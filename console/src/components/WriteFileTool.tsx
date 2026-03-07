import { Markdown, ToolCall } from "@agentscope-ai/chat";

interface WriteFileToolProps {
  data: any;
}

export default function WriteFileTool({ data }: WriteFileToolProps) {
  if (!data.content?.length) return null;

  const content = data.content as any[];
  const toolOutput = content[1]?.data?.output;

  // Extract text content from output (handle both string and array formats)
  let outputText: string | undefined;

  if (typeof toolOutput === 'string') {
    outputText = toolOutput;
  } else if (Array.isArray(toolOutput) && toolOutput.length > 0) {
    // Handle array format: [{type: "text", text: "..."}]
    outputText = toolOutput[0]?.text;
  }

  // If output contains markdown download link, render it as Markdown
  if (outputText && outputText.includes('[') && outputText.includes('](')) {
    return (
      <div style={{ padding: '8px 0' }}>
        <Markdown content={outputText} />
      </div>
    );
  }

  // Fallback to default ToolCall render
  return <ToolCall loading={false} defaultOpen={false} title="write_file" input={content[0]?.data?.arguments} output={toolOutput} />;
}
