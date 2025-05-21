from datetime import datetime, timezone
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
    cast,
)

from loguru import logger
from pydantic import (
    BaseModel,
    ValidationError,
    field_validator,
    model_validator,
)

from open_notebook.database.repository import (
    repo_create,
    repo_delete,
    repo_query,
    repo_relate,
    repo_update,
    repo_upsert,
)
from open_notebook.exceptions import (
    DatabaseOperationError,
    InvalidInputError,
    NotFoundError,
)

T = TypeVar("T", bound="ObjectModel")


class ObjectModel(BaseModel):
    id: Optional[str] = None
    table_name: ClassVar[str] = ""
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    class Config:
        validate_assignment = True
        arbitrary_types_allowed = True

    @classmethod
    def get_all(cls: Type[T], order_by=None) -> List[T]:
        try:
            # If called from a specific subclass, use its table_name
            if cls.table_name:
                target_class = cls
                table_name = cls.table_name
            else:
                # This path is taken if called directly from ObjectModel
                raise InvalidInputError(
                    "get_all() must be called from a specific model class"
                )

            if order_by:
                order = f" ORDER BY {order_by}"
            else:
                order = ""

            result = repo_query(f"SELECT * FROM {table_name} {order}")
            objects = []
            for obj in result:
                try:
                    objects.append(target_class(**obj))
                except Exception as e:
                    logger.critical(f"Error creating object: {str(e)}")

            return objects
        except Exception as e:
            logger.error(f"Error fetching all {cls.table_name}: {str(e)}")
            logger.exception(e)
            raise DatabaseOperationError(e)

    @classmethod
    def get(cls: Type[T], id: str) -> T:
        if not id:
            raise InvalidInputError("ID cannot be empty")
        try:
            # Get the table name from the ID (everything before the first colon)
            table_name = id.split(":")[0] if ":" in id else id

            # If we're calling from a specific subclass and IDs match, use that class
            if cls.table_name and cls.table_name == table_name:
                target_class: Type[T] = cls
            else:
                # Otherwise, find the appropriate subclass based on table_name
                found_class = cls._get_class_by_table_name(table_name)
                if not found_class:
                    raise InvalidInputError(f"No class found for table {table_name}")
                target_class = cast(Type[T], found_class)

            result = repo_query(f"SELECT * FROM {id}")
            if result:
                return target_class(**result[0])
            else:
                raise NotFoundError(f"{table_name} with id {id} not found")
        except Exception as e:
            logger.error(f"Error fetching object with id {id}: {str(e)}")
            logger.exception(e)
            raise NotFoundError(f"Object with id {id} not found - {str(e)}")

    @classmethod
    def _get_class_by_table_name(cls, table_name: str) -> Optional[Type["ObjectModel"]]:
        """Find the appropriate subclass based on table_name."""

        def get_all_subclasses(c: Type["ObjectModel"]) -> List[Type["ObjectModel"]]:
            all_subclasses: List[Type["ObjectModel"]] = []
            for subclass in c.__subclasses__():
                all_subclasses.append(subclass)
                all_subclasses.extend(get_all_subclasses(subclass))
            return all_subclasses

        for subclass in get_all_subclasses(ObjectModel):
            if hasattr(subclass, "table_name") and subclass.table_name == table_name:
                return subclass
        return None

    def needs_embedding(self) -> bool:
        return False

    def get_embedding_content(self) -> Optional[str]:
        return None

    def save(self) -> None:
        from open_notebook.domain.models import model_manager

        try:
            # self.model_validate(self.model_dump(), strict=True) # Validation on assignment should cover this

            data_for_db = self.model_dump(exclude_none=True)

            # Embedding logic
            if self.needs_embedding():
                embedding_content = self.get_embedding_content()
                if embedding_content:
                    EMBEDDING_MODEL = model_manager.embedding_model
                    if not EMBEDDING_MODEL:
                        logger.warning(
                            "No embedding model found. Content will not be searchable."
                        )
                    data_for_db["embedding"] = (
                        EMBEDDING_MODEL.embed(embedding_content)
                        if EMBEDDING_MODEL
                        else []
                    )
            
            # Standardize created/updated to ISO Z format for DB
            current_time_iso_z = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            data_for_db["updated"] = current_time_iso_z

            # Remove id from data_for_db as it's handled by repo_create/repo_update argument
            # or is None for create.
            id_to_save = data_for_db.pop("id", None) # Use self.id for updates, id is None for creates

            if self.id is None: # Creating new
                data_for_db["created"] = current_time_iso_z
                repo_result = repo_create(self.__class__.table_name, data_for_db)
            else: # Updating existing
                if self.created: # self.created should be a datetime object
                    data_for_db["created"] = self.created.isoformat().replace("+00:00", "Z")
                # If self.created was None, model_dump(exclude_none=True) would have removed 'created' key.
                # If 'created' is missing and it's an update, it remains as is in the DB.
                
                logger.debug(f"Updating record with id {self.id}")
                repo_result = repo_update(self.id, data_for_db)

            # Update the current instance with the result
            if repo_result and repo_result[0]: # Check if repo_result is not empty
                for key, value in repo_result[0].items():
                    if hasattr(self, key):
                        # With validate_assignment=True, setattr should trigger validators
                        if isinstance(getattr(self, key), BaseModel) and isinstance(value, dict):
                            setattr(self, key, type(getattr(self, key))(**value))
                        else:
                            setattr(self, key, value)
            else:
                logger.warning(f"Save operation for {self.__class__.table_name} (id: {self.id}) did not return expected result.")


        except ValidationError as e:
            logger.error(f"Validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Error saving record: {e}")
            raise

        except Exception as e:
            logger.error(f"Error saving {self.__class__.table_name}: {str(e)}")
            logger.exception(e)
            raise DatabaseOperationError(e)

    def _prepare_save_data(self) -> Dict[str, Any]:
        data = self.model_dump()
        return {key: value for key, value in data.items() if value is not None}

    def delete(self) -> bool:
        if self.id is None:
            raise InvalidInputError("Cannot delete object without an ID")
        try:
            logger.debug(f"Deleting record with id {self.id}")
            return repo_delete(self.id)
        except Exception as e:
            logger.error(
                f"Error deleting {self.__class__.table_name} with id {self.id}: {str(e)}"
            )
            raise DatabaseOperationError(
                f"Failed to delete {self.__class__.table_name}"
            )

    def relate(
        self, relationship: str, target_id: str, data: Optional[Dict] = {}
    ) -> Any:
        if not relationship or not target_id or not self.id:
            raise InvalidInputError("Relationship and target ID must be provided")
        try:
            return repo_relate(
                source=self.id, relationship=relationship, target=target_id, data=data
            )
        except Exception as e:
            logger.error(f"Error creating relationship: {str(e)}")
            logger.exception(e)
            raise DatabaseOperationError(e)

    @field_validator("created", "updated", mode="before")
    @classmethod
    def parse_datetime(cls, value):
        if isinstance(value, str):
            try:
                # Attempt to parse ISO format (handles 'Z' for UTC)
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                try:
                    # Attempt to parse format like 'YYYY-MM-DD HH:MM:SS' (common in save method)
                    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    logger.warning(f"Could not parse datetime string '{value}'. Returning as is.")
                    return value # Or return None, or raise a custom error
        return value


class RecordModel(BaseModel):
    record_id: ClassVar[str]
    auto_save: ClassVar[bool] = (
        False  # Default to False, can be overridden in subclasses
    )
    _instances: ClassVar[Dict[str, "RecordModel"]] = {}  # Store instances by record_id

    class Config:
        validate_assignment = True
        arbitrary_types_allowed = True
        extra = "allow"
        from_attributes = True
        defer_build = True

    def __new__(cls, **kwargs):
        # If an instance already exists for this record_id, return it
        if cls.record_id in cls._instances:
            instance = cls._instances[cls.record_id]
            # Update instance with any new kwargs if provided
            if kwargs:
                for key, value in kwargs.items():
                    setattr(instance, key, value)
            return instance

        # If no instance exists, create a new one
        instance = super().__new__(cls)
        cls._instances[cls.record_id] = instance
        return instance

    def __init__(self, **kwargs):
        # Only initialize if this is a new instance
        if not hasattr(self, "_initialized"):
            object.__setattr__(self, "__dict__", {})
            # Load data from DB first
            result = repo_query(f"SELECT * FROM {self.record_id};")

            # Initialize with DB data and any overrides
            init_data = {}
            if result and result[0]:
                init_data.update(result[0])

            # Override with any provided kwargs
            if kwargs:
                init_data.update(kwargs)

            # Initialize base model first
            super().__init__(**init_data)

            # Mark as initialized
            object.__setattr__(self, "_initialized", True)

    @classmethod
    def get_instance(cls) -> "RecordModel":
        """Get or create the singleton instance"""
        return cls()

    @model_validator(mode="after")
    def auto_save_validator(self):
        if self.__class__.auto_save:
            self.update()
        return self

    def update(self):
        # Get all non-ClassVar fields and their values
        data_to_upsert = {
            field_name: getattr(self, field_name)
            for field_name, field_info in self.model_fields.items()
            if not str(field_info.annotation).startswith("typing.ClassVar")
        }

        # Standardize datetime format for DB
        # 'created' should reflect its current state on the model, but formatted
        if "created" in data_to_upsert and isinstance(data_to_upsert["created"], datetime):
            data_to_upsert["created"] = data_to_upsert["created"].isoformat().replace("+00:00", "Z")
        
        # 'updated' should always be the current time for an update operation
        data_to_upsert["updated"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        # Remove 'id' if present, as record_id is used
        if "id" in data_to_upsert:
            del data_to_upsert["id"]


        repo_upsert(self.record_id, data_to_upsert)

        result = repo_query(f"SELECT * FROM {self.record_id};")
        if result and result[0]:
            for key, value in result[0].items():
                if hasattr(self, key):
                    if key in ("created", "updated"):
                        # Manually parse datetime strings since object.__setattr__ bypasses Pydantic validators
                        parsed_value = ObjectModel.parse_datetime(value)
                        object.__setattr__(self, key, parsed_value)
                    else:
                        object.__setattr__(self, key, value)
        return self

    @classmethod
    def clear_instance(cls):
        """Clear the singleton instance (useful for testing)"""
        if cls.record_id in cls._instances:
            del cls._instances[cls.record_id]

    def patch(self, model_dict: dict):
        """Update model attributes from dictionary and save"""
        for key, value in model_dict.items():
            setattr(self, key, value)
        self.update()
