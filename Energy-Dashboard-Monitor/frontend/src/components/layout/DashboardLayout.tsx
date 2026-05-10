
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopBar from './TopBar';

const DashboardLayout = () => {
  return (
    <div className="flex bg-background text-on-surface min-h-screen font-body-md overflow-x-hidden">
      <Sidebar />
      <TopBar />
      <main className="ml-[280px] mt-16 p-container-margin flex-1 w-full">
        <Outlet />
      </main>
    </div>
  );
};

export default DashboardLayout;
