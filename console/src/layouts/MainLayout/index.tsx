import { Layout } from "antd";
import { useEffect } from "react";
import { Routes, Route, useLocation, useNavigate, Navigate } from "react-router-dom";
import Sidebar from "../Sidebar";
import Header from "../Header";
import ConsoleCronBubble from "../../components/ConsoleCronBubble";
import Chat from "../../pages/Chat";
import ChannelsPage from "../../pages/Control/Channels";
import SessionsPage from "../../pages/Control/Sessions";
import CronJobsPage from "../../pages/Control/CronJobs";
import TasksPage from "../../pages/Control/Tasks";
import AgentConfigPage from "../../pages/Agent/Config";
import SkillsPage from "../../pages/Agent/Skills";
import WorkspacePage from "../../pages/Agent/Workspace";
import MCPPage from "../../pages/Agent/MCP";
import AgentInstancesPage from "../../pages/Agent/Instances";
import ModelsPage from "../../pages/Settings/Models";
import EnvironmentsPage from "../../pages/Settings/Environments";
import RulesPage from "../../pages/Settings/Rules";

const { Content } = Layout;

const pathToKey: Record<string, string> = {
  "/chat": "chat",
  "/channels": "channels",
  "/sessions": "sessions",
  "/cron-jobs": "cron-jobs",
  "/tasks": "tasks",
  "/skills": "skills",
  "/mcp": "mcp",
  "/workspace": "workspace",
  "/agent-instances": "agent-instances",
  "/agent-config": "agent-config",
  "/models": "models",
  "/environments": "environments",
  "/rules": "rules",
};

export default function MainLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const currentPath = location.pathname;
  const selectedKey = pathToKey[currentPath] || "chat";

  useEffect(() => {
    if (currentPath === "/") {
      navigate("/chat", { replace: true });
    }
  }, [currentPath, navigate]);

  return (
    <Layout style={{ height: "100vh" }}>
      <Sidebar selectedKey={selectedKey} />
      <Layout>
        <Header selectedKey={selectedKey} />
        <Content className="page-container">
          <ConsoleCronBubble />
          <div className="page-content">
            <Routes>
              <Route path="/chat" element={<Chat />} />
              <Route path="/channels" element={<ChannelsPage />} />
              <Route path="/sessions" element={<SessionsPage />} />
              <Route path="/cron-jobs" element={<CronJobsPage />} />
              <Route path="/tasks" element={<TasksPage />} />
              <Route path="/skills" element={<SkillsPage />} />
              <Route path="/mcp" element={<MCPPage />} />
              <Route path="/workspace" element={<WorkspacePage />} />
              <Route path="/models" element={<ModelsPage />} />
              <Route path="/environments" element={<EnvironmentsPage />} />
              <Route path="/rules" element={<RulesPage />} />
              <Route path="/agent-instances" element={<AgentInstancesPage />} />
              <Route path="/agent-config" element={<AgentConfigPage />} />
              {/* Redirect old /personas route to /agent-instances */}
              <Route path="/personas" element={<Navigate to="/agent-instances" replace />} />
              <Route path="/" element={<Chat />} />
            </Routes>
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
