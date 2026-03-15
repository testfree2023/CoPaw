import {
  AgentScopeRuntimeWebUI,
  IAgentScopeRuntimeWebUIOptions,
} from "@agentscope-ai/chat";
import { useMemo, useState, useEffect } from "react";
import { Modal, Button, Result } from "antd";
import { ExclamationCircleOutlined, SettingOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import sessionApi from "./sessionApi";
import { useLocalStorageState } from "ahooks";
import defaultConfig, { DefaultConfig } from "./OptionsPanel/defaultConfig";
import Weather from "./Weather";
import { getApiUrl, getApiToken } from "../../api/config";
import { providerApi } from "../../api/modules/provider";
import WriteFileTool from "../../components/WriteFileTool";
import { TaskProgressDisplay } from "../../components/TaskProgressDisplay";
import { useTaskProgress } from "../../hooks/useTaskProgress";
import "./index.module.less";

interface CustomWindow extends Window {
  currentSessionId?: string;
  currentUserId?: string;
  currentChannel?: string;
}

declare const window: CustomWindow;

type OptionsConfig = DefaultConfig;

export default function ChatPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [showModelPrompt, setShowModelPrompt] = useState(false);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [optionsConfig] = useLocalStorageState<OptionsConfig>(
    "agent-scope-runtime-webui-options",
    {
      defaultValue: defaultConfig,
      listenStorageChange: true,
    },
  );

  // Subscribe to task progress
  const taskProgress = useTaskProgress(currentTaskId);

  // Auto-clear task progress when completed
  useEffect(() => {
    if (taskProgress.status === 'completed' || taskProgress.status === 'failed') {
      const timer = setTimeout(() => {
        setCurrentTaskId(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [taskProgress.status]);

  const handleConfigureModel = () => {
    setShowModelPrompt(false);
    navigate("/models");
  };

  const handleSkipConfiguration = () => {
    setShowModelPrompt(false);
  };

  const options = useMemo(() => {
    const handleModelError = () => {
      setShowModelPrompt(true);
      return new Response(
        JSON.stringify({
          error: "Model not configured",
          message: "Please configure a model first",
        }),
        {
          status: 400,
          headers: { "Content-Type": "application/json" },
        },
      );
    };

    const customFetch = async (data: {
      input: any[];
      biz_params?: any;
    }): Promise<Response> => {
      try {
        const activeModels = await providerApi.getActiveModels();

        if (
          !activeModels?.active_llm?.provider_id ||
          !activeModels?.active_llm?.model
        ) {
          return handleModelError();
        }
      } catch (error) {
        console.error("Failed to check model configuration:", error);
        return handleModelError();
      }

      const { input, biz_params } = data;

      const lastMessage = input[input.length - 1];
      const session = lastMessage?.session || {};

      const session_id = window.currentSessionId || session?.session_id || "";
      const user_id = window.currentUserId || session?.user_id || "default";
      const channel = window.currentChannel || session?.channel || "console";

      // Transform input format from @agentscope-ai/chat to AgentRequest format
      // Chat package sends: {type: "text", text: "..."}
      // Backend expects: {type: "text", content: [{type: "text", text: "..."}]}
      const transformInput = (messages: any[]) => {
        return messages.map(msg => {
          if (msg.type === "text" && msg.text) {
            return {
              type: msg.type,
              content: [{ type: "text", text: msg.text }]
            };
          }
          // Pass through other message types unchanged
          return msg;
        });
      };

      const requestBody = {
        input: transformInput(input.slice(-1)),
        session_id,
        user_id,
        channel,
        stream: true,
        ...biz_params,
      };

      const headers: HeadersInit = {
        "Content-Type": "application/json",
      };

      const token = getApiToken();
      if (token) {
        (headers as Record<string, string>).Authorization = `Bearer ${token}`;
      }

      const url = optionsConfig?.api?.baseURL || getApiUrl("/agent/process");

      // Make the fetch request
      const response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(requestBody),
      });

      // Clone the response to read the body without consuming it
      const clone = response.clone();

      // Try to extract task ID from response
      // For streaming responses, we need to read the full text first
      clone.text().then(text => {
        console.log('[ChatPage] Response text:', text.substring(0, 200));
        try {
          const data = JSON.parse(text);
          // Check if response contains task_id (from task creation message)
          if (data?.content && typeof data.content === 'string') {
            const taskIdMatch = data.content.match(/任务 ID: ([a-f0-9-]+)/i);
            if (taskIdMatch) {
              const taskId = taskIdMatch[1];
              console.log('[ChatPage] Detected task ID:', taskId);
              setCurrentTaskId(taskId);
            } else {
              console.log('[ChatPage] No task ID found in response:', data.content);
            }
          } else {
            console.log('[ChatPage] Response content not string:', data?.content);
          }
        } catch (err) {
          // For streaming responses, parse line by line
          console.log('[ChatPage] Parsing as stream:', text.substring(0, 100));
          const lines = text.split('\n');
          for (const line of lines) {
            if (line.trim()) {
              try {
                const data = JSON.parse(line);
                if (data?.content && typeof data.content === 'string') {
                  const taskIdMatch = data.content.match(/任务 ID: ([a-f0-9-]+)/i);
                  if (taskIdMatch) {
                    const taskId = taskIdMatch[1];
                    console.log('[ChatPage] Detected task ID from stream:', taskId);
                    setCurrentTaskId(taskId);
                    break;
                  }
                }
              } catch {
                // Ignore invalid JSON lines
              }
            }
          }
        }
      }).catch((err) => {
        console.error('[ChatPage] Failed to read response text:', err);
      });

      return response;
    };

    return {
      ...optionsConfig,
      session: {
        multiple: true,
        api: sessionApi,
      },
      theme: {
        ...optionsConfig.theme,
      },
      api: {
        ...optionsConfig.api,
        fetch: customFetch,
        cancel(data: { session_id: string }) {
          console.log(data);
        },
      },
      customToolRenderConfig: {
        "weather search mock": Weather,
        "write_file": WriteFileTool,
      },
    } as unknown as IAgentScopeRuntimeWebUIOptions;
  }, [optionsConfig]);

  return (
    <div style={{ height: "100%", width: "100%", position: "relative" }}>
      <AgentScopeRuntimeWebUI options={options} />

      {/* Task Progress Panel */}
      {currentTaskId && (
        <div style={{
          position: 'absolute',
          bottom: 20,
          right: 20,
          width: 380,
          maxHeight: 400,
          overflow: 'auto',
          zIndex: 1000,
        }}>
          <TaskProgressDisplay taskId={currentTaskId} progress={taskProgress} />
        </div>
      )}

      <Modal open={showModelPrompt} closable={false} footer={null} width={480}>
        <Result
          icon={<ExclamationCircleOutlined style={{ color: "#faad14" }} />}
          title={t("modelConfig.promptTitle")}
          subTitle={t("modelConfig.promptMessage")}
          extra={[
            <Button key="skip" onClick={handleSkipConfiguration}>
              {t("modelConfig.skipButton")}
            </Button>,
            <Button
              key="configure"
              type="primary"
              icon={<SettingOutlined />}
              onClick={handleConfigureModel}
            >
              {t("modelConfig.configureButton")}
            </Button>,
          ]}
        />
      </Modal>
    </div>
  );
}
