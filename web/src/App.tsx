/**
 * Точка ветвления: вошёл человек или нет.
 *
 * Пока идёт проверка токена — ни каркаса, ни формы: мелькание формы входа у
 * вошедшего человека читается как разлогинивание.
 */
import { Center, Loader } from '@mantine/core';
import { BrowserRouter } from 'react-router-dom';

import { AppRoutes } from './app/routes';
import { Shell } from './app/Shell';
import { AuthProvider, useAuth } from './auth/AuthProvider';
import { LoginPage } from './pages/LoginPage';

function Gate() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    );
  }
  if (!user) return <LoginPage />;
  return (
    <Shell>
      <AppRoutes />
    </Shell>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Gate />
      </AuthProvider>
    </BrowserRouter>
  );
}
