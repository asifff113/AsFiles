
import { FormEvent, useState, useCallback, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import { Tool, ToolConfig, ToolStatus } from "../config/tools";
import { Button } from "./ui/Button";
import { FormField } from "./ui/FormField";
import * as LucideIcons from "lucide-react";

interface ActivePanelProps {
  tool: Tool;
}

interface FileItem {
  id: string;
  file: File;
}

const makeId = () => Math.random().toString(36).substring(2, 9);
const formatBytes = (bytes: number) => {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / 1024 ** i).toFixed(1)} ${units[i]}`;
};

// Helper to convert text to different formats
const downloadAsFormat = (text: string, filename: string, format: 'txt' | 'md' | 'html' | 'json') => {
  let content = text;
  let mimeType = 'text/plain';
  let ext = format;

  if (format === 'html') {
    content = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${filename}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }
    h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
    pre { background: #f4f4f4; padding: 15px; border-radius: 8px; overflow-x: auto; }
  </style>
</head>
<body>
  <h1>AI Generated Result</h1>
  <div>${text.replace(/\n/g, '<br>')}</div>
</body>
</html>`;
    mimeType = 'text/html';
  } else if (format === 'md') {
    content = `# AI Generated Result\n\n${text}`;
    mimeType = 'text/markdown';
  } else if (format === 'json') {
    content = JSON.stringify({ result: text, generated: new Date().toISOString() }, null, 2);
    mimeType = 'application/json';
  }

  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${filename}.${ext}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

export const ActivePanel = ({ tool }: ActivePanelProps) => {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [status, setStatus] = useState<"idle" | "working" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [formValues, setFormValues] = useState<Record<string, any>>({});
  const [aiResult, setAiResult] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [outputFileName, setOutputFileName] = useState<string>("");

  // Check if this is an AI tool
  const isAITool = tool.category === "ai";

  // Copy to clipboard with feedback
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Reset when tool changes
  useEffect(() => {
    setFiles([]);
    setStatus("idle");
    setErrorMsg(null);
    setDownloadUrl(null);
    setAiResult(null);
    setCopied(false);
    setOutputFileName("");
    if (tool.config?.formFields) {
      const initial: Record<string, any> = {};
      tool.config.formFields.forEach(f => initial[f.name] = f.defaultValue);
      setFormValues(initial);
    } else {
      setFormValues({});
    }
  }, [tool.id]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (!tool.config) return;
    const newFiles = acceptedFiles.map(f => ({ id: makeId(), file: f }));
    
    if (tool.config.multiFile) {
        setFiles(prev => {
            // Filter duplicates
            const existingNames = new Set(prev.map(p => p.file.name));
            const unique = newFiles.filter(n => !existingNames.has(n.file.name));
            return [...prev, ...unique];
        });
    } else {
        setFiles([newFiles[0]]); // Replace if single file
    }
    setStatus("idle");
  }, [tool.config]);

  // Map file extensions to MIME types
  const getMimeTypes = (extensions: string[]) => {
    const mimeMap: Record<string, string[]> = {
      '.pdf': ['application/pdf'],
      '.pptx': ['application/vnd.openxmlformats-officedocument.presentationml.presentation'],
      '.ppt': ['application/vnd.ms-powerpoint'],
      '.docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
      '.doc': ['application/msword'],
      '.xlsx': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
      '.xls': ['application/vnd.ms-excel'],
      '.jpg': ['image/jpeg'],
      '.jpeg': ['image/jpeg'],
      '.png': ['image/png'],
      '.gif': ['image/gif'],
      '.bmp': ['image/bmp'],
      '.webp': ['image/webp'],
    };
    
    const result: Record<string, string[]> = {};
    extensions.forEach(ext => {
      if (mimeMap[ext]) {
        result[mimeMap[ext][0]] = [ext];
      }
    });
    return result;
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: tool.config?.acceptedFiles ? getMimeTypes(tool.config.acceptedFiles) : undefined,
    multiple: tool.config?.multiFile
  });

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!tool.config) return;
    
    if (tool.config.acceptedFiles.length > 0 && files.length < (tool.config.minFiles || 1)) {
      setStatus("error");
      setErrorMsg(`Please select at least ${tool.config.minFiles || 1} file(s).`);
      return;
    }

    setStatus("working");
    setErrorMsg(null);
    setAiResult(null);

    const formData = new FormData();
    files.forEach(f => formData.append(tool.config!.multiFile ? "files" : "file", f.file));
    
    Object.entries(formValues).forEach(([key, val]) => {
      formData.append(key, String(val));
    });

    try {
      const apiUrl = (import.meta.env?.VITE_API_URL as string) || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}${tool.config.endpoint}`, {
        method: tool.config.method,
        body: formData,
      });

      if (!response.ok) {
        throw new Error(await response.text() || "Processing failed");
      }

      // For AI tools, read as text and display in UI
      if (isAITool) {
        const text = await response.text();
        setAiResult(text);
        setStatus("success");
      } else {
        // For other tools, create download blob
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        setDownloadUrl(url);
        
        // Generate output filename based on uploaded file
        const outputExt = tool.config.outputFileName.split('.').pop() || 'pdf';
        if (files.length === 1) {
          // Single file: use original name with new extension
          const baseName = files[0].name.replace(/\.[^/.]+$/, '');
          setOutputFileName(`${baseName}.${outputExt}`);
        } else if (files.length > 1) {
          // Multiple files: use first file name + merged/combined
          const baseName = files[0].name.replace(/\.[^/.]+$/, '');
          setOutputFileName(`${baseName}_merged.${outputExt}`);
        } else {
          setOutputFileName(tool.config.outputFileName);
        }
        setStatus("success");
      }
    } catch (err: any) {
      console.error(err);
      setStatus("error");
      setErrorMsg(err.message || "Something went wrong.");
    }
  };

  // Get the icon component dynamically
  const IconComponent = (LucideIcons as unknown as Record<string, LucideIcons.LucideIcon>)[tool.icon] || LucideIcons.File;

  if (tool.status !== "ready" || !tool.config) {
    return (
      <div className="text-center py-20">
        <div className={`inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br ${tool.accent} mb-6 opacity-50`}>
          <IconComponent className="text-white" size={40} />
        </div>
        <h2 className="text-2xl font-bold mb-2">Coming Soon</h2>
        <p className="text-gray-400 max-w-md mx-auto">
          We are currently building this feature. Check back later for updates!
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-10 text-center">
        <span className={`inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br ${tool.accent} mb-4 shadow-xl`}>
          <IconComponent className="text-white" size={32} />
        </span>
        <h2 className="text-4xl font-bold mb-3">{tool.title}</h2>
        <p className="text-gray-400 text-lg">{tool.description}</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-8 glass-panel p-8 rounded-3xl relative overflow-hidden">
        {/* Decorative glow */}
        <div className={`absolute top-0 left-1/2 -translate-x-1/2 w-64 h-64 bg-gradient-to-br ${tool.accent} blur-[100px] opacity-10 pointer-events-none`} />

        {/* Dropzone */}
        {tool.config.acceptedFiles.length > 0 && (
          <div
            {...getRootProps()}
            className={`
              border-2 border-dashed rounded-2xl p-10 text-center transition-all cursor-pointer bottom-0
              ${isDragActive ? "border-primary bg-primary/10 scale-[1.02]" : "border-white/10 hover:border-white/20 hover:bg-white/5"}
            `}
          >
            <input {...getInputProps()} />
            <div className="text-4xl mb-4 opacity-50">📂</div>
            <p className="text-lg font-medium mb-1">
              Drag & drop {tool.config.acceptedFiles.join(", ")} here
            </p>
            <p className="text-sm text-gray-500">
              or click to browse from your computer
            </p>
          </div>
        )}

        {/* File List */}
        {files.length > 0 && (
            <div className="bg-black/20 rounded-xl overflow-hidden border border-white/5">
                <div className="px-4 py-3 bg-white/5 flex justify-between items-center text-sm font-medium">
                    <span>{files.length} file{files.length > 1 ? 's' : ''} selected</span>
                    <button type="button" onClick={() => setFiles([])} className="text-red-400 hover:text-red-300">Clear All</button>
                </div>
                <div className="max-h-60 overflow-y-auto divide-y divide-white/5">
                    {files.map((f, i) => (
                        <div key={f.id} className="px-4 py-3 flex justify-between items-center hover:bg-white/5 transition-colors">
                            <div className="flex items-center gap-3 overflow-hidden">
                                <span className="text-gray-500 w-6 font-mono text-xs">{i + 1}</span>
                                <span className="truncate max-w-[200px] sm:max-w-md">{f.file.name}</span>
                                <span className="text-xs text-gray-500 bg-white/5 px-2 py-0.5 rounded">{formatBytes(f.file.size)}</span>
                            </div>
                            <button
                                type="button"
                                onClick={() => setFiles(prev => prev.filter(p => p.id !== f.id))}
                                className="text-gray-500 hover:text-red-400 px-2"
                            >
                                ×
                            </button>
                        </div>
                    ))}
                </div>
            </div>
        )}

        {/* Config Fields */}
        {tool.config.formFields && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 bg-white/5 p-6 rounded-xl border border-white/5">
             <div className="col-span-full text-xs font-bold uppercase tracking-wider text-gray-500">Configuration</div>
            {tool.config.formFields.map(field => (
              <FormField
                key={field.name}
                field={field}
                value={formValues[field.name]}
                onChange={(name, val) => setFormValues(prev => ({ ...prev, [name]: val }))}
              />
            ))}
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-4 pt-4 border-t border-white/10">
            <Button
                type="submit"
                size="lg"
                disabled={status === 'working'}
                className="flex-1"
                variant={status === 'error' ? 'danger' : 'primary'}
            >
                {status === 'working' ? (
                   <span className="flex items-center gap-2">
                       <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                           <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                           <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                       </svg>
                       Processing...
                   </span>
                ) : status === 'error' ? 'Failed - Try Again' : `Process ${tool.title}`}
            </Button>
            
            {downloadUrl && !isAITool && (
                <a
                    href={downloadUrl}
                    download={outputFileName || tool.config.outputFileName}
                    className="flex-1"
                >
                    <Button type="button" variant="success" size="lg" className="w-full animate-bounce-subtle">
                        Download Result
                    </Button>
                </a>
            )}
        </div>
        
        {/* AI Result Display */}
        {aiResult && isAITool && (
          <div className="mt-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <LucideIcons.Sparkles className="text-violet-400" size={20} />
                AI Result
              </h3>
              <span className="text-xs text-gray-400 bg-white/5 px-2 py-1 rounded">
                {aiResult.length} characters
              </span>
            </div>
            
            {/* Result Text Area */}
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-br from-violet-500/10 to-purple-600/10 rounded-xl blur-xl" />
              <div className="relative bg-black/40 border border-white/10 rounded-xl p-6 max-h-96 overflow-y-auto">
                <pre className="whitespace-pre-wrap text-gray-200 font-sans text-sm leading-relaxed">
                  {aiResult}
                </pre>
              </div>
              {/* Copy button */}
              <button
                type="button"
                onClick={() => copyToClipboard(aiResult)}
                className={`absolute top-3 right-3 p-2 rounded-lg transition-all ${
                  copied 
                    ? 'bg-green-500/30 text-green-400' 
                    : 'bg-white/10 hover:bg-white/20 text-gray-400'
                }`}
                title={copied ? "Copied!" : "Copy to clipboard"}
              >
                {copied ? (
                  <LucideIcons.Check size={16} />
                ) : (
                  <LucideIcons.Copy size={16} />
                )}
              </button>
            </div>
            
            {/* Download Options */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <p className="text-sm text-gray-400 mb-3 flex items-center gap-2">
                <LucideIcons.Download size={16} />
                Download as:
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => downloadAsFormat(aiResult, tool.id + '-result', 'txt')}
                  className="px-4 py-2 bg-blue-500/20 hover:bg-blue-500/30 text-blue-300 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                >
                  <LucideIcons.FileText size={16} />
                  .TXT
                </button>
                <button
                  type="button"
                  onClick={() => downloadAsFormat(aiResult, tool.id + '-result', 'md')}
                  className="px-4 py-2 bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                >
                  <LucideIcons.FileCode size={16} />
                  .MD
                </button>
                <button
                  type="button"
                  onClick={() => downloadAsFormat(aiResult, tool.id + '-result', 'html')}
                  className="px-4 py-2 bg-orange-500/20 hover:bg-orange-500/30 text-orange-300 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                >
                  <LucideIcons.Globe size={16} />
                  .HTML
                </button>
                <button
                  type="button"
                  onClick={() => downloadAsFormat(aiResult, tool.id + '-result', 'json')}
                  className="px-4 py-2 bg-green-500/20 hover:bg-green-500/30 text-green-300 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                >
                  <LucideIcons.Braces size={16} />
                  .JSON
                </button>
              </div>
            </div>
          </div>
        )}
        
        {errorMsg && (
            <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-200 rounded-lg text-sm text-center">
                {errorMsg}
            </div>
        )}

      </form>
    </div>
  );
};
