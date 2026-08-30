import { BrowserRouter, useNavigate, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import { Providers } from './providers';
import { AppRoutes } from './routes';

function AppNavigationHandler() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // On initial app load, always redirect to dashboard
    // Check if we're not already on dashboard and this is a fresh page load
    if (location.pathname !== '/' && !sessionStorage.getItem('app_initialized')) {
      navigate('/', { replace: true });
    }
    // Mark app as initialized for this session
    sessionStorage.setItem('app_initialized', 'true');
  }, []);

  return <AppRoutes />;
}

export function App() {
  return (
    <BrowserRouter>
      <Providers>
        <AppNavigationHandler />
      </Providers>
    </BrowserRouter>
  );
}
