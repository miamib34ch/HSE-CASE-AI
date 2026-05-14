import { createBrowserRouter } from "react-router-dom";
import { AppLayout } from "../layouts/app-layout";
import { AgentsPage } from "../pages/agents-page";
import { DashboardPage } from "../pages/dashboard-page";
import { McpPage } from "../pages/mcp-page";
import { ProjectPage } from "../pages/project-page";
import { ProvidersPage } from "../pages/providers-page";
import { LogsPage } from "../pages/logs-page";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "/projects/:projectId", element: <ProjectPage /> },
      { path: "/providers", element: <ProvidersPage /> },
      { path: "/mcp", element: <McpPage /> },
      { path: "/agents", element: <AgentsPage /> },
      { path: "/logs", element: <LogsPage /> },
    ],
  },
]);
