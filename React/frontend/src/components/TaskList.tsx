import React, { useState, useEffect, useCallback } from 'react';
import type { Task } from '../types';
import { fetchTasksByNotebookId, createTask, updateTask, deleteTask } from '../services/api';

interface TaskListProps {
  notebookId: string;
}

const TaskList: React.FC<TaskListProps> = ({ notebookId }) => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [newTaskDescription, setNewTaskDescription] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState('');

  const loadTasks = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const fetchedTasks = await fetchTasksByNotebookId(notebookId);
      setTasks(fetchedTasks.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tasks');
      console.error(err);
    }
    setIsLoading(false);
  }, [notebookId]);

  useEffect(() => {
    if (notebookId) {
      loadTasks();
    }
  }, [notebookId, loadTasks]);

  const handleAddTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskDescription.trim()) return;
    setError(null);
    try {
      const newTask = await createTask(notebookId, newTaskDescription, 'todo');
      setTasks(prevTasks => [newTask, ...prevTasks].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()));
      setNewTaskDescription('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add task');
      console.error(err);
    }
  };

  const handleToggleStatus = async (task: Task) => {
    const newStatus = task.status === 'todo' ? 'in_progress' : task.status === 'in_progress' ? 'completed' : 'todo';
    setError(null);
    try {
      const updated = await updateTask(task.id, { status: newStatus });
      setTasks(prevTasks => 
        prevTasks.map(t => t.id === task.id ? updated : t)
                 .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update task status');
      console.error(err);
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    setError(null);
    try {
      await deleteTask(taskId);
      setTasks(prevTasks => prevTasks.filter(t => t.id !== taskId)
                                   .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete task');
      console.error(err);
    }
  };

  const startEdit = (task: Task) => {
    setEditingTaskId(task.id);
    setEditingText(task.description);
  };

  const handleUpdateDescription = async (taskId: string) => {
    if (!editingText.trim()) return;
    setError(null);
    try {
      const updated = await updateTask(taskId, { description: editingText });
      setTasks(prevTasks => 
        prevTasks.map(t => t.id === taskId ? updated : t)
                 .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      );
      setEditingTaskId(null);
      setEditingText('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update task description');
      console.error(err);
    }
  };

  if (isLoading) return <p>Loading tasks...</p>;

  return (
    <div className="tasks-section" style={{ marginTop: '20px' }}>
      <h3>Tasks</h3>
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      <form onSubmit={handleAddTask} style={{ marginBottom: '10px' }}>
        <input 
          type="text" 
          value={newTaskDescription} 
          onChange={(e) => setNewTaskDescription(e.target.value)} 
          placeholder="Add a new task" 
          style={{ marginRight: '5px' }}
        />
        <button type="submit">Add Task</button>
      </form>
      <ul style={{ listStyle: 'none', paddingLeft: 0 }}>
        {tasks.map(task => (
          <li key={task.id} style={{ marginBottom: '10px', padding: '5px', border: '1px solid #eee', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            {editingTaskId === task.id ? (
              <input 
                type="text"
                value={editingText}
                onChange={(e) => setEditingText(e.target.value)}
                onBlur={() => handleUpdateDescription(task.id)} // Save on blur
                onKeyPress={(e) => e.key === 'Enter' && handleUpdateDescription(task.id)} // Save on Enter
                autoFocus
                style={{ flexGrow: 1, marginRight: '10px' }}
              />
            ) : (
              <span 
                onClick={() => handleToggleStatus(task)} 
                style={{
                  textDecoration: task.status === 'completed' ? 'line-through' : 'none',
                  cursor: 'pointer',
                  flexGrow: 1,
                }}
                title={`Status: ${task.status} (Click to cycle)`}
              >
                {task.description}
              </span>
            )}
            <div>
              {editingTaskId !== task.id && (
                <button onClick={() => startEdit(task)} style={{ marginRight: '5px' }}>Edit</button>
              )}
              <button onClick={() => handleDeleteTask(task.id)}>Delete</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default TaskList; 