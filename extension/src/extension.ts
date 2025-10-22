import * as vscode from "vscode";
import { TextDecoder } from "util";


/** Entry point — registers commands and the side chat panel. */
export function activate(context: vscode.ExtensionContext) {
  console.log("[OurProject-1] activate()");

  // Quick access: status bar button to open the side chat
  const sb = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  sb.text = "$(comment-discussion) OurProject-1";
  sb.tooltip = "Open OurProject-1 Side Chat";
  sb.command = "multiModalDebug.openChat";
  sb.show();
  context.subscriptions.push(sb);

  // Analyze the active editor (selection or entire document), with sendPath toggle
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.analyzeActive", async (arg?: any) => {
      const sendPath = !!(arg && arg.sendPath);
      const ed = vscode.window.activeTextEditor;
      let sourcePath: string | undefined;
      let raw: string | undefined;
      let usedSelection = false;

      if (ed) {
        const doc = ed.document;
        const sel = ed.selection;
        usedSelection = !!(sel && !sel.isEmpty);
        raw = usedSelection ? doc.getText(sel) : doc.getText();
        sourcePath = doc.uri?.fsPath;
        if (!raw && !sendPath) {
          vscode.window.showWarningMessage("Active editor is empty.");
          return;
        }
      } else {
        // Fallback to last cached content (from a previous Read/Write/Analyze)
        const cached = ChatPanel.getCached();
        raw = cached.body;
        sourcePath = cached.path;
        if (!raw && !sourcePath) {
          vscode.window.showWarningMessage("No active editor to analyze, and no cached file. Use 'Read File' or open a file in the editor.");
          return;
        }
      }

      try {
        let result: any;
        let pathForDisplay = sourcePath;

        if (sendPath && sourcePath && !usedSelection) {
          // Let the server read the file by path (enables .ipynb cell extraction & size clamping server-side)
          result = await analyzeWithBackendPayload({
            repo: ".",
            path: sourcePath,
            screenshot_b64: null,
          });
        } else {
          const { maxPayload, notebookStrategy } = getSettings();
          const prepared = prepareTextForAnalysis(sourcePath, raw || "", { limit: maxPayload, notebookStrategy });
          result = await analyzeWithBackend(prepared.text);
          // Attach a small note so users know when we transformed/truncated data client-side
          if (prepared.note) {
            result = { ...result, _note: prepared.note };
          }
        }

        // Ensure the panel exists and remember input
        ChatPanel.createOrShow(context);
        ChatPanel.remember(sourcePath, raw);
        await ChatPanel.postMessage({ type: "analysisResult", path: pathForDisplay, body: result });
      } catch (e: any) {
        vscode.window.showErrorMessage(`Analyze Active failed: ${e?.message ?? String(e)}`);
      }
    })
  );

  // Copy last analysis JSON to clipboard
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.copyAnalysis", async () => {
      const last = ChatPanel.getLastAnalysis();
      if (!last?.body) { vscode.window.showWarningMessage("No analysis available to copy."); return; }
      await vscode.env.clipboard.writeText(JSON.stringify(last.body, null, 2));
      vscode.window.showInformationMessage("Analysis copied to clipboard.");
    })
  );

  // Save last analysis as Markdown (docs/incidents/INCIDENT_*.md)
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.saveAnalysis", async () => {
      const last = ChatPanel.getLastAnalysis();
      if (!last?.body) { vscode.window.showWarningMessage("No analysis available to save."); return; }
      const md = makeIncidentMarkdown(last.body, last.path);

      const ws = vscode.workspace.workspaceFolders?.[0]?.uri;
      let target: vscode.Uri | undefined;
      if (ws) {
        const dir = vscode.Uri.joinPath(ws, "docs", "incidents");
        try { await vscode.workspace.fs.createDirectory(dir); } catch {}
        const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+$/, "");
        target = vscode.Uri.joinPath(dir, `INCIDENT_${stamp}.md`);
      } else {
        target = await vscode.window.showSaveDialog({
          saveLabel: "Save Incident Report",
          filters: { Markdown: ["md"] },
        });
        if (!target) return;
      }
      await vscode.workspace.fs.writeFile(target, Buffer.from(md));
      vscode.window.showInformationMessage(`Incident report saved → ${target.fsPath}`);
    })
  );

  // Open side chat
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.openChat", () => {
      ChatPanel.createOrShow(context);
    })
  );

  // Ping
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.helloWorld", () => {
      vscode.window.showInformationMessage(
        "Multi-Modal Debugging Agent Extension Running 🚀"
      );
      ChatPanel.postMessage({ type: "status", message: "hello-from-command" });
    })
  );

  // Read file (Command Palette)
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.readFile", async () => {
      const uri = await pickFileToRead();
      if (!uri) return;
      const { text, size } = await readFileText(uri);
      vscode.window.showInformationMessage(`Read ${uri.fsPath} (${size} bytes)`);
      ChatPanel.postMessage({ type: "fileContent", path: uri.fsPath, body: text });
    })
  );

  // Write file (Command Palette)
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.writeFile", async () => {
      const uri = await pickFileToWrite();
      if (!uri) return;
      const content = await vscode.window.showInputBox({
        prompt: "Enter file content",
        placeHolder: "Type text to save…",
      });
      if (content === undefined) return; // cancelled
      await vscode.workspace.fs.writeFile(uri, Buffer.from(content));
      vscode.window.showInformationMessage(`Wrote ${uri.fsPath}`);
      ChatPanel.postMessage({ type: "fileWritten", path: uri.fsPath, body: content });
    })
  );

  // Analyze via Backend (Picker) — forwards to panel with sendPath=true
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.analyzeBackend", async () => {
      ChatPanel.createOrShow(context);
      await ChatPanel.postMessage({ type: "analyze", sendPath: true });
    })
  );

  // Command Palette helpers for panel actions
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.previewReport", async () => {
      ChatPanel.createOrShow(context);
      await ChatPanel.postMessage({ type: "previewReport" });
    })
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.openLocation", async () => {
      ChatPanel.createOrShow(context);
      await ChatPanel.postMessage({ type: "openLocation" });
    })
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.savePatch", async () => {
      ChatPanel.createOrShow(context);
      await ChatPanel.postMessage({ type: "savePatch" });
    })
  );
  // NEW: Apply Patch
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.applyPatch", async () => {
      ChatPanel.createOrShow(context);
      await ChatPanel.postMessage({ type: "applyPatch" });
    })
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.saveTest", async () => {
      ChatPanel.createOrShow(context);
      await ChatPanel.postMessage({ type: "saveTest" });
    })
  );
  // NEW: Insert Test
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.insertTest", async () => {
      ChatPanel.createOrShow(context);
      await ChatPanel.postMessage({ type: "insertTest" });
    })
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.copyRCA", async () => {
      ChatPanel.createOrShow(context);
      await ChatPanel.postMessage({ type: "copyRCA" });
    })
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.clearHistory", async () => {
      ChatPanel.createOrShow(context);
      await ChatPanel.postMessage({ type: "clearHistory" });
    })
  );

  // Runner: Run Tests from backend
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.runTests", async () => {
      ChatPanel.createOrShow(context);
      await ChatPanel.postMessage({ type: "runTests" });
    })
  );

  // Runner: Run arbitrary shell command on backend
  context.subscriptions.push(
    vscode.commands.registerCommand("multiModalDebug.runCommand", async () => {
      ChatPanel.createOrShow(context);
      await ChatPanel.postMessage({ type: "runCommand" });
    })
  );
}

export function deactivate() {}


/** Settings helpers */
function getBackendBase(): string {
  const cfg = vscode.workspace.getConfiguration("multiModalDebug");
  const deprecated = (cfg.get<string>("backendUrl") || "").trim();
  const base = (deprecated || cfg.get<string>("backendBase") || "http://127.0.0.1:8000").replace(/\/$/, "");
  return base;
}
function getSettings() {
  const cfg = vscode.workspace.getConfiguration("multiModalDebug");
  const maxPayload = cfg.get<number>("maxPayload") ?? 2_097_152; // ~2MB
  const notebookStrategy = (cfg.get<string>("notebookStrategy") || "cells") as "cells" | "raw";
  return { maxPayload, notebookStrategy };
}

/* ---------------- helpers ---------------- */

async function pickFileToRead(): Promise<vscode.Uri | undefined> {
  const uri = await vscode.window.showOpenDialog({
    canSelectFolders: false,
    canSelectMany: false,
    openLabel: "Pick file to read",
    defaultUri: vscode.workspace.workspaceFolders?.[0]?.uri,
  });
  return uri?.[0];
}

async function pickFileToWrite(): Promise<vscode.Uri | undefined> {
  const defaultUri = vscode.workspace.workspaceFolders?.[0]?.uri;
  return vscode.window.showSaveDialog({ defaultUri, saveLabel: "Save content" });
}

async function readFileText(uri: vscode.Uri): Promise<{ text: string; size: number }> {
  const buf = await vscode.workspace.fs.readFile(uri);
  const text = new TextDecoder().decode(buf);
  return { text, size: buf.byteLength };
}

/**
 * If the file is a Jupyter notebook (.ipynb), try to extract a readable
 * plaintext representation (concatenated source of code/markdown cells).
 * Returns null if parsing fails or file is not a notebook.
 */
function extractNotebookText(path: string | undefined, body: string): string | null {
  try {
    if (!path || !path.toLowerCase().endsWith(".ipynb")) return null;
    const nb = JSON.parse(body);
    if (!Array.isArray(nb?.cells)) return null;
    const pieces: string[] = [];
    for (const cell of nb.cells) {
      const src = Array.isArray(cell?.source) ? cell.source.join("") : (cell?.source ?? "");
      const tag = cell?.cell_type === "markdown" ? "md" : "code";
      pieces.push(`\n# [${tag}]\n${src}`);
    }
    return pieces.join("\n").trim();
  } catch {
    return null;
  }
}

/** Clamp very large text to avoid sending megabytes to the backend. */
function clampText(s: string, limit = 200_000): { text: string; truncated: boolean } {
  if (s.length <= limit) return { text: s, truncated: false };
  return { text: s.slice(0, limit), truncated: true };
}

/**
 * Prepare text that will be sent to the backend:
 * - If a .ipynb is detected, extract cell text (configurable).
 * - Clamp to a safe size and attach a note when truncation happens.
 */
function prepareTextForAnalysis(
  path: string | undefined,
  raw: string,
  opts?: { limit?: number; notebookStrategy?: "cells" | "raw" }
): { text: string; note?: string } {
  const { limit = 200_000, notebookStrategy = "cells" } = opts || {};
  const nbText = notebookStrategy === "cells" ? extractNotebookText(path, raw) : null;
  const { text, truncated } = clampText(nbText ?? raw, limit);
  return {
    text,
    note: [
      nbText ? "Converted from .ipynb" : undefined,
      truncated ? "Truncated large input for performance" : undefined,
    ].filter(Boolean).join("; ") || undefined,
  };
}

/** Calls the FastAPI RCA endpoint with either {log} or {path}. */
async function analyzeWithBackendPayload(payload: any): Promise<any> {
  const res = await fetch(`${getBackendBase()}/api/v1/incidents/rca`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errTxt = await res.text().catch(() => "");
    throw new Error(`Backend ${res.status}: ${errTxt || res.statusText}`);
  }
  return res.json();
}

/** Calls the FastAPI RCA endpoint using Node-side fetch (no CORS issues). */
async function analyzeWithBackend(logText: string): Promise<any> {
  return analyzeWithBackendPayload({ repo: ".", log: logText, screenshot_b64: null });
}

/** Runner helpers */
async function runnerPytest(payload: { path: string; quiet?: boolean }): Promise<any> {
  const res = await fetch(`${getBackendBase()}/api/v1/runner/pytest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errTxt = await res.text().catch(() => "");
    throw new Error(`Runner pytest ${res.status}: ${errTxt || res.statusText}`);
  }
  return res.json();
}

async function runnerRun(payload: { cmd: string; cwd?: string; shell?: boolean }): Promise<any> {
  const res = await fetch(`${getBackendBase()}/api/v1/runner/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errTxt = await res.text().catch(() => "");
    throw new Error(`Runner run ${res.status}: ${errTxt || res.statusText}`);
  }
  return res.json();
}

function makeIncidentMarkdown(data: any, sourcePath?: string): string {
  const rca = typeof data === "string" ? data : data?.rca ?? data;
  const patch = data?.patch ?? null;
  const test = data?.test ?? null;
  const exception = data?.exception ?? null;
  const file = data?.file ?? (sourcePath || null);
  const note = data?._note || data?.note || null;
  const context = Array.isArray(data?.context) ? data.context : null;

  const now = new Date();
  const ts = now.toISOString();
  const src = sourcePath ?? "(unknown)";

  const headerLines: string[] = [
    `# Incident Report`,
    ``,
    `- **Timestamp:** ${ts}`,
    `- **Source:** \`${src}\``,
  ];
  if (exception || file || note) {
    headerLines.push(`- **Summary:**`);
    if (exception) headerLines.push(`  - Exception: \`${exception}\``);
    if (file) headerLines.push(`  - Location: \`${file}\``);
    if (note) headerLines.push(`  - Note: ${note}`);
  }

  const sections: string[] = [];
  sections.push(
    `## Root Cause Analysis`,
    "```text",
    typeof rca === "string" ? rca : JSON.stringify(rca, null, 2),
    "```",
    ``
  );

  if (context && context.length) {
    sections.push(
      `## Context`,
      "```text",
      context.join("\n"),
      "```",
      ``
    );
  }

  if (patch) {
    sections.push(
      `## Suggested Patch`,
      "```diff",
      typeof patch === "string" ? patch : JSON.stringify(patch, null, 2),
      "```",
      ``
    );
  }

  if (test) {
    sections.push(
      `## Suggested Test`,
      "```",
      typeof test === "string" ? test : JSON.stringify(test, null, 2),
      "```",
      ``
    );
  }

  return [...headerLines, ...sections].filter(Boolean).join("\n");
}

/* ---------------- webview panel ---------------- */

type PanelMsg =
  | { type: "status"; message: string }
  | { type: "error"; message: string }
  | { type: "fileContent"; path: string; body: string }
  | { type: "fileWritten"; path: string; body: string }
  | { type: "analysisResult"; path?: string; body: any }
  | { type: "readFile" }
  | { type: "writeFile" }
  | { type: "overwriteFile" }
  | { type: "analyze"; sendPath?: boolean }
  | { type: "analyzeActive"; sendPath?: boolean }
  | { type: "saveReport" }
  | { type: "copyAnalysis" }
  | { type: "copyRCA" }
  | { type: "clearHistory" }
  | { type: "openLocation" }
  | { type: "previewReport" }
  | { type: "savePatch" }
  | { type: "applyPatch" }   // added
  | { type: "saveTest" }
  | { type: "insertTest" }   // added
  | { type: "historyPrev" }
  | { type: "historyNext" }
  | { type: "runTests" }
  | { type: "runCommand" }
  | { type: "runnerResult"; body: any };

class ChatPanel {
  static readonly viewType = "multiModalDebug.chat";
  static currentPanel: ChatPanel | undefined;

  private disposables: vscode.Disposable[] = [];
  private lastPath?: string;
  private lastBody?: string;
  private lastAnalysis?: { path?: string; body: any };
  private history: { path?: string; body: any; ts: number }[] = [];
  private historyIndex: number = -1;

  public static getLastAnalysis(): { path?: string; body: any } | undefined {
    return ChatPanel.currentPanel?.lastAnalysis;
  }
  public static remember(path?: string, body?: string) {
    if (ChatPanel.currentPanel) {
      ChatPanel.currentPanel.lastPath = path;
      ChatPanel.currentPanel.lastBody = body;
    }
  }
  public static getCached(): { path?: string; body?: string } {
    return ChatPanel.currentPanel
      ? { path: ChatPanel.currentPanel.lastPath, body: ChatPanel.currentPanel.lastBody }
      : {};
  }

  private pushHistory(entry: { path?: string; body: any }) {
    // If we navigated back, drop any forward entries
    if (this.historyIndex < this.history.length - 1) {
      this.history = this.history.slice(0, this.historyIndex + 1);
    }
    const e = { ...entry, ts: Date.now() };
    this.history.push(e);
    this.historyIndex = this.history.length - 1;
    this.lastAnalysis = { path: e.path, body: e.body };
  }

  private navigateHistory(delta: number) {
    if (!this.history.length) return;
    let idx = this.historyIndex + delta;
    idx = Math.max(0, Math.min(this.history.length - 1, idx));
    this.historyIndex = idx;
    const e = this.history[idx];
    this.lastAnalysis = { path: e.path, body: e.body };
    this.panel.webview.postMessage({ type: "analysisResult", path: e.path, body: e.body });
    this.status(`history: ${idx + 1}/${this.history.length}`);
  }

  private clearHistory() {
    this.history = [];
    this.historyIndex = -1;
    this.lastAnalysis = undefined;
  }

  private constructor(
    private readonly panel: vscode.WebviewPanel,
    private readonly extensionUri: vscode.Uri
  ) {
    this.panel.webview.html = this.getHtmlForWebview(this.panel.webview);

    this.panel.webview.onDidReceiveMessage(
      async (msg: PanelMsg) => {
        try {
          switch (msg?.type) {
            case "runTests": {
              // Pick a sensible default tests path (backend runs with CWD=backend/)
              const ws = vscode.workspace.workspaceFolders?.[0]?.uri;
              let defaultPath = "../tests/backend";
              try {
                if (ws) {
                  // Prefer repo-level tests/backend if present
                  await vscode.workspace.fs.stat(vscode.Uri.joinPath(ws, "tests", "backend"));
                  defaultPath = "../tests/backend";
                }
              } catch {
                try {
                  if (ws) {
                    await vscode.workspace.fs.stat(vscode.Uri.joinPath(ws, "backend", "tests"));
                    defaultPath = "tests";
                  }
                } catch {}
              }

              const path = await vscode.window.showInputBox({
                prompt: "Pytest path (relative to backend working dir)",
                value: defaultPath,
                placeHolder: "../tests/backend or tests",
              });
              if (!path) { this.status("runTests:cancelled"); break; }

              await vscode.window.withProgress(
                { location: vscode.ProgressLocation.Notification, title: "Running tests…" },
                async () => {
                  const out = await runnerPytest({ path, quiet: true });
                  this.panel.webview.postMessage({ type: "runnerResult", body: out });
                  this.status("runTests: done");
                }
              );
              break;
            }

            case "runCommand": {
              const cmd = await vscode.window.showInputBox({
                prompt: "Shell command to run on backend",
                value: "pytest -q",
              });
              if (!cmd) { this.status("runCommand:cancelled"); break; }
              await vscode.window.withProgress(
                { location: vscode.ProgressLocation.Notification, title: "Running command…" },
                async () => {
                  const out = await runnerRun({ cmd, shell: true });
                  this.panel.webview.postMessage({ type: "runnerResult", body: out });
                  this.status("runCommand: done");
                }
              );
              break;
            }
            case "copyRCA": {
              const body = this.lastAnalysis?.body;
              const rcaText = typeof body?.rca === "string" ? body.rca : (body?.rca ? JSON.stringify(body.rca, null, 2) : undefined);
              if (!rcaText) { this.status("copyRCA: no rca to copy"); break; }
              await vscode.env.clipboard.writeText(rcaText);
              vscode.window.showInformationMessage("RCA copied to clipboard.");
              this.status("copyRCA: copied");
              break;
            }
            case "clearHistory": {
              this.clearHistory();
              this.status("history cleared");
              break;
            }
            case "readFile": {
              const uri = await pickFileToRead();
              if (!uri) return this.status("read:cancelled");
              const { text } = await readFileText(uri);
              this.lastPath = uri.fsPath;
              this.lastBody = text;
              this.panel.webview.postMessage({ type: "fileContent", path: uri.fsPath, body: text });
              break;
            }
            case "writeFile": {
              const uri = await pickFileToWrite();
              if (!uri) return this.status("write:cancelled");
              const content = await vscode.window.showInputBox({
                prompt: "Enter file content",
                placeHolder: "Type text to save…",
              });
              if (content === undefined) return this.status("write:cancelled");
              await vscode.workspace.fs.writeFile(uri, Buffer.from(content));
              this.lastPath = uri.fsPath;
              this.lastBody = content;
              this.panel.webview.postMessage({ type: "fileWritten", path: uri.fsPath, body: content });
              break;
            }
            case "overwriteFile": {
              const open = await vscode.window.showOpenDialog({
                canSelectFolders: false,
                canSelectMany: false,
                openLabel: "Pick file to overwrite",
                defaultUri: vscode.workspace.workspaceFolders?.[0]?.uri,
              });
              const uri = open?.[0];
              if (!uri) return this.status("overwrite:cancelled");
              const content = await vscode.window.showInputBox({
                prompt: `Overwrite ${uri.fsPath} with:`,
                placeHolder: "Type replacement content…",
              });
              if (content === undefined) return this.status("overwrite:cancelled");
              await vscode.workspace.fs.writeFile(uri, Buffer.from(content));
              this.lastPath = uri.fsPath;
              this.lastBody = content;
              this.panel.webview.postMessage({ type: "fileWritten", path: uri.fsPath, body: content });
              break;
            }
            case "analyze": {
              const sendPath = (msg as any)?.sendPath === true;
              const hasCached = typeof this.lastBody === "string" && this.lastBody.length > 0;
              let path = this.lastPath;
              let textToAnalyze = this.lastBody;

              let picked: vscode.Uri | undefined;
              if (!hasCached && !sendPath) {
                // If we're sending file content, we need to read it now
                picked = await pickFileToRead();
                if (!picked) return this.status("analyze:cancelled");
              }
              if (!hasCached && sendPath) {
                // If the server will read the file, just pick a path
                picked = await pickFileToRead();
                if (!picked) return this.status("analyze:cancelled");
                path = picked.fsPath;
                this.lastPath = path;
              }

              await vscode.window.withProgress(
                { location: vscode.ProgressLocation.Notification, title: "Analyzing via backend…" },
                async () => {
                  let result: any;

                  if (sendPath && path) {
                    // Server reads the file by path
                    result = await analyzeWithBackendPayload({ repo: ".", path, screenshot_b64: null });
                  } else {
                    if (!hasCached && picked) {
                      const { text } = await readFileText(picked);
                      textToAnalyze = text;
                      path = picked.fsPath;
                      // cache for subsequent clicks
                      this.lastPath = path;
                      this.lastBody = text;
                    }
                    const { maxPayload, notebookStrategy } = getSettings();
                    const prepared = prepareTextForAnalysis(path, textToAnalyze || "", { limit: maxPayload, notebookStrategy });
                    result = await analyzeWithBackend(prepared.text);
                    if (prepared.note) {
                      result = { ...result, _note: prepared.note };
                    }
                  }

                  this.pushHistory({ path, body: result });
                  this.panel.webview.postMessage({ type: "analysisResult", path, body: result });
                }
              );
              break;
            }
            case "openLocation": {
              const last = this.lastAnalysis?.body;
              const fileField: string | undefined = last?.file;
              if (!fileField) { this.status("openLocation: no file in last analysis"); break; }
              // Accept formats like "/path/to/file.py:123" or "file.py:123:45"
              const m = /^(.*?):(\d+)(?::\d+)?$/.exec(fileField);
              const rel = fileField.replace(/:\d+(?::\d+)?$/, "");
              let targetPath = m ? m[1] : rel;
              let line = m ? parseInt(m[2], 10) - 1 : 0;

              try {
                let docUri: vscode.Uri | undefined;
                const candidate = vscode.Uri.file(targetPath);
                try {
                  await vscode.workspace.fs.stat(candidate);
                  docUri = candidate;
                } catch {
                  const ws = vscode.workspace.workspaceFolders?.[0]?.uri;
                  if (ws) {
                    const alt = vscode.Uri.joinPath(ws, targetPath);
                    await vscode.workspace.fs.stat(alt);
                    docUri = alt;
                  }
                }
                if (!docUri) { this.status("openLocation: file not found in workspace"); break; }
                const doc = await vscode.workspace.openTextDocument(docUri);
                const ed = await vscode.window.showTextDocument(doc, { preview: true });
                const pos = new vscode.Position(Math.max(0, line), 0);
                ed.selection = new vscode.Selection(pos, pos);
                ed.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
              } catch {
                this.status("openLocation: failed to open file");
              }
              break;
            }
            case "previewReport": {
              if (!this.lastAnalysis?.body) { this.status("preview: no analysis"); break; }
              const md = makeIncidentMarkdown(this.lastAnalysis.body, this.lastAnalysis.path);
              const doc = await vscode.workspace.openTextDocument({ content: md, language: "markdown" });
              await vscode.window.showTextDocument(doc, { preview: true });
              this.status("preview: opened Markdown report");
              break;
            }
            case "savePatch": {
              const patch = this.lastAnalysis?.body?.patch;
              if (!patch) { this.status("patch: none available"); break; }
              const ws = vscode.workspace.workspaceFolders?.[0]?.uri;
              const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+$/, "");
              let target = ws ? vscode.Uri.joinPath(ws, "patches", `suggested_${stamp}.patch`) : undefined;
              if (target) {
                try { await vscode.workspace.fs.createDirectory(vscode.Uri.joinPath(ws!, "patches")); } catch {}
              } else {
                target = await vscode.window.showSaveDialog({ saveLabel: "Save Patch", filters: { Patch: ["patch", "diff"] } });
                if (!target) { this.status("patch:cancelled"); break; }
              }
              await vscode.workspace.fs.writeFile(target!, Buffer.from(String(patch)));
              vscode.window.showInformationMessage(`Saved patch → ${target!.fsPath}`);
              this.status("patch: saved");
              break;
            }
            // --- inserted new cases for applyPatch and insertTest ---
            case "applyPatch": {
              const patch = this.lastAnalysis?.body?.patch;
              if (!patch) { this.status("apply-patch: none available"); break; }
              const ws = vscode.workspace.workspaceFolders?.[0]?.uri;
              if (!ws) { this.status("apply-patch: no workspace open"); break; }
              const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+$/, "");
              const patchesDir = vscode.Uri.joinPath(ws, "patches");
              try { await vscode.workspace.fs.createDirectory(patchesDir); } catch {}
              const patchUri = vscode.Uri.joinPath(patchesDir, `suggested_${stamp}.patch`);
              await vscode.workspace.fs.writeFile(patchUri, Buffer.from(String(patch)));
              const term = vscode.window.createTerminal({ name: "OurProject-1: apply patch", cwd: ws.fsPath });
              term.show();
              term.sendText(`git apply --reject --whitespace=fix "${patchUri.fsPath}"`);
              vscode.window.showInformationMessage(`Saved patch → ${patchUri.fsPath}. Running 'git apply' in terminal.`);
              this.status("apply-patch: invoked git apply");
              break;
            }
            case "insertTest": {
              const test = this.lastAnalysis?.body?.test;
              if (!test) { this.status("insert-test: none available"); break; }
              const ws = vscode.workspace.workspaceFolders?.[0]?.uri;
              let target: vscode.Uri | undefined;
              const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+$/, "");
              if (ws) {
                // Prefer backend/tests if it exists; else tests/
                let testsDir = vscode.Uri.joinPath(ws, "backend", "tests");
                try { await vscode.workspace.fs.stat(testsDir); } catch { testsDir = vscode.Uri.joinPath(ws, "tests"); }
                try { await vscode.workspace.fs.createDirectory(testsDir); } catch {}
                target = vscode.Uri.joinPath(testsDir, `rca_test_${stamp}.py`);
              } else {
                target = await vscode.window.showSaveDialog({ saveLabel: "Save Test", filters: { Python: ["py"], All: ["*"] } });
                if (!target) { this.status("insert-test:cancelled"); break; }
              }
              await vscode.workspace.fs.writeFile(target!, Buffer.from(String(test)));
              const doc = await vscode.workspace.openTextDocument(target!);
              await vscode.window.showTextDocument(doc, { preview: true });
              vscode.window.showInformationMessage(`Inserted test → ${target!.fsPath}`);
              this.status("insert-test: saved & opened");
              break;
            }
            // --- end new cases ---
            case "saveTest": {
              const test = this.lastAnalysis?.body?.test;
              if (!test) { this.status("test: none available"); break; }
              const ws = vscode.workspace.workspaceFolders?.[0]?.uri;
              const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+$/, "");
              let target = ws ? vscode.Uri.joinPath(ws, "tests", `rca_test_${stamp}.py`) : undefined;
              if (target) {
                try { await vscode.workspace.fs.createDirectory(vscode.Uri.joinPath(ws!, "tests")); } catch {}
              } else {
                target = await vscode.window.showSaveDialog({ saveLabel: "Save Test", filters: { "Python": ["py"], "All": ["*"] } });
                if (!target) { this.status("test:cancelled"); break; }
              }
              await vscode.workspace.fs.writeFile(target!, Buffer.from(String(test)));
              vscode.window.showInformationMessage(`Saved test → ${target!.fsPath}`);
              this.status("test: saved");
              break;
            }
            case "historyPrev": {
              this.navigateHistory(-1);
              break;
            }
            case "historyNext": {
              this.navigateHistory(1);
              break;
            }
            case "analyzeActive": {
              // Delegate to the existing command with toggle flag
              const sendPath = (msg as any)?.sendPath === true;
              this.status("analyzeActive: using active editor/selection…");
              await vscode.commands.executeCommand("multiModalDebug.analyzeActive", { sendPath });
              break;
            }
            case "saveReport": {
              if (!this.lastAnalysis?.body) { this.status("save: no analysis"); break; }
              const md = makeIncidentMarkdown(this.lastAnalysis.body, this.lastAnalysis.path);
              const ws = vscode.workspace.workspaceFolders?.[0]?.uri;
              let target: vscode.Uri | undefined;
              if (ws) {
                const dir = vscode.Uri.joinPath(ws, "docs", "incidents");
                try { await vscode.workspace.fs.createDirectory(dir); } catch {}
                const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+$/, "");
                target = vscode.Uri.joinPath(dir, `INCIDENT_${stamp}.md`);
              } else {
                target = await vscode.window.showSaveDialog({
                  saveLabel: "Save Incident Report",
                  filters: { Markdown: ["md"] },
                });
                if (!target) { this.status("save:cancelled"); break; }
              }
              await vscode.workspace.fs.writeFile(target, Buffer.from(md));
              this.status(`saved: ${target.fsPath}`);
              vscode.window.showInformationMessage(`Incident report saved → ${target.fsPath}`);
              break;
            }
            case "copyAnalysis": {
              if (!this.lastAnalysis?.body) { this.status("copy: no analysis"); break; }
              await vscode.env.clipboard.writeText(JSON.stringify(this.lastAnalysis.body, null, 2));
              this.status("copy: analysis copied to clipboard");
              vscode.window.showInformationMessage("Analysis copied to clipboard.");
              break;
            }
            default:
              this.status(`unknown:${String((msg as any)?.type)}`);
          }
        } catch (err: any) {
          const message = err?.message ?? String(err);
          console.error("[OurProject-1] webview msg error:", message);
          this.panel.webview.postMessage({ type: "error", message });
        }
      },
      undefined,
      this.disposables
    );

    this.panel.onDidDispose(() => this.dispose(), null, this.disposables);
  }

  static createOrShow(context: vscode.ExtensionContext) {
    const column = vscode.window.activeTextEditor?.viewColumn ?? vscode.ViewColumn.Beside;
    if (ChatPanel.currentPanel) {
      ChatPanel.currentPanel.panel.reveal(column);
      return;
    }
    const panel = vscode.window.createWebviewPanel(
      ChatPanel.viewType,
      "OurProject-1 Side Chat",
      column,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
      }
    );
    ChatPanel.currentPanel = new ChatPanel(panel, context.extensionUri);
  }

  static async postMessage(message: PanelMsg) {
    if (!ChatPanel.currentPanel) {
      console.log("[OurProject-1] postMessage dropped (no panel):", (message as any)?.type);
      return;
    }
    // keep cache in sync when messages originate from command palette
    if (message.type === "fileContent" || message.type === "fileWritten") {
      ChatPanel.currentPanel.lastPath = (message as any).path;
      ChatPanel.currentPanel.lastBody = (message as any).body ?? "";
    }
    if (message.type === "analysisResult") {
      const path = (message as any).path;
      const body = (message as any).body;
      ChatPanel.currentPanel.lastAnalysis = { path, body };
      ChatPanel.currentPanel.pushHistory({ path, body });
    }
    try {
      const ok = await ChatPanel.currentPanel.panel.webview.postMessage(message);
      console.log(
        "[OurProject-1] postMessage",
        (message as any)?.type,
        ok ? "delivered" : "not-delivered"
      );
    } catch (err: any) {
      console.error("[OurProject-1] postMessage error:", err?.message ?? String(err));
    }
  }

  private status(message: string) {
    this.panel.webview.postMessage({ type: "status", message });
  }

  dispose() {
    ChatPanel.currentPanel = undefined;
    while (this.disposables.length) {
      try {
        this.disposables.pop()?.dispose();
      } catch {}
    }
  }

  private getHtmlForWebview(webview: vscode.Webview): string {
    // CSP: no network calls from webview; all HTTP happens on extension host.
    const nonce = getNonce();
    const csp =
      `default-src 'none'; ` +
      `img-src ${webview.cspSource} https: data:; ` +
      `style-src ${webview.cspSource} 'unsafe-inline'; ` +
      `script-src 'nonce-${nonce}';`;

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="${csp}">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OurProject-1 Side Chat</title>
  <style>
    :root { color-scheme: var(--vscode-color-scheme, light dark); }
    body { font-family: var(--vscode-font-family); margin: 0; }
    header { padding: 8px 12px; background: var(--vscode-editor-background); border-bottom: 1px solid var(--vscode-panel-border); }
    main { padding: 12px; display: grid; gap: 8px; }
    textarea { width: 100%; height: 320px; resize: vertical; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; }
    button { padding: 6px 10px; }
    code { white-space: pre-wrap; }
    .busy {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: color-mix(in oklab, var(--vscode-editor-background) 70%, transparent);
      backdrop-filter: blur(2px);
      font-weight: 600;
      letter-spacing: 0.3px;
      visibility: hidden;
    }
    .busy.show { visibility: visible; }
  </style>
</head>
<body>
  <header>OurProject-1 — Side Chat</header>
  <main style="position:relative;">
    <div class="row">
      <button id="btn-read">Read File</button>
      <button id="btn-write">Write File</button>
      <button id="btn-overwrite">Overwrite File</button>
      <button id="btn-analyze">Analyze via Backend</button>
      <button id="btn-analyze-active">Analyze Active Editor</button>
      <button id="btn-open-loc">Open Location</button>
      <button id="btn-preview">Preview Report</button>
      <button id="btn-copy">Copy Analysis</button>
      <button id="btn-copy-rca">Copy RCA</button>
      <button id="btn-save">Save Report</button>
      <button id="btn-save-patch">Save Patch</button>
      <button id="btn-apply-patch">Apply Patch</button>
      <button id="btn-save-test">Save Test</button>
      <button id="btn-insert-test">Insert Test</button>
      <button id="btn-run-tests">Run Tests</button>
      <button id="btn-run-cmd">Run Cmd</button>
      <button id="btn-clear">Clear</button>
      <label style="margin-left:auto; display:flex; align-items:center; gap:6px;">
        <input type="checkbox" id="opt-send-path">
        <span>Server reads file (send path)</span>
      </label>
      <div style="display:flex; align-items:center; gap:4px;">
        <button id="btn-prev" title="Previous Analysis">◀</button>
        <button id="btn-next" title="Next Analysis">▶</button>
      </div>
    </div>
    <div id="busy" class="busy">Analyzing…</div>
    <textarea id="output" placeholder="Use the buttons above. Messages will appear here..." readonly></textarea>
  </main>

  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const out = document.getElementById('output');
    const state = vscode.getState() || {};
    const chkSendPath = document.getElementById('opt-send-path');
    if (chkSendPath) {
      chkSendPath.checked = !!state.sendPath;
      chkSendPath.addEventListener('change', () => {
        const st = vscode.getState() || {};
        st.sendPath = !!chkSendPath.checked;
        vscode.setState(st);
      });
    }
    function log(line) { out.value = (out.value ? out.value + "\\n" : "") + line; }
    const busyEl = document.getElementById('busy');
    function setBusy(on) {
      busyEl.classList.toggle('show', !!on);
    }
    log('[ready] webview loaded');

    document.getElementById('btn-read').addEventListener('click', () => {
      log('[ui] read clicked — opening picker…');
      vscode.postMessage({ type: 'readFile' });
    });

    document.getElementById('btn-write').addEventListener('click', () => {
      log('[ui] write clicked — opening picker…');
      vscode.postMessage({ type: 'writeFile' });
    });

    document.getElementById('btn-overwrite').addEventListener('click', () => {
      log('[ui] overwrite clicked — opening picker…');
      vscode.postMessage({ type: 'overwriteFile' });
    });

    document.getElementById('btn-analyze').addEventListener('click', () => {
      log('[ui] analyze clicked — using last file if available (otherwise picker)…');
      setBusy(true);
      vscode.postMessage({ type: 'analyze', sendPath: !!(chkSendPath && chkSendPath.checked) });
    });

    document.getElementById('btn-analyze-active').addEventListener('click', () => {
      log('[ui] analyze-active clicked — using current editor/selection (or cached content)…');
      setBusy(true);
      vscode.postMessage({ type: 'analyzeActive', sendPath: !!(chkSendPath && chkSendPath.checked) });
    });

    document.getElementById('btn-copy').addEventListener('click', () => {
      vscode.postMessage({ type: 'copyAnalysis' });
    });
    document.getElementById('btn-copy-rca').addEventListener('click', () => {
      vscode.postMessage({ type: 'copyRCA' });
    });

    document.getElementById('btn-save').addEventListener('click', () => {
      vscode.postMessage({ type: 'saveReport' });
    });

    document.getElementById('btn-open-loc').addEventListener('click', () => {
      vscode.postMessage({ type: 'openLocation' });
    });
    document.getElementById('btn-preview').addEventListener('click', () => {
      vscode.postMessage({ type: 'previewReport' });
    });
    document.getElementById('btn-save-patch').addEventListener('click', () => {
      vscode.postMessage({ type: 'savePatch' });
    });
    document.getElementById('btn-apply-patch').addEventListener('click', () => {
      vscode.postMessage({ type: 'applyPatch' });
    });
    document.getElementById('btn-save-test').addEventListener('click', () => {
      vscode.postMessage({ type: 'saveTest' });
    });
    document.getElementById('btn-insert-test').addEventListener('click', () => {
      vscode.postMessage({ type: 'insertTest' });
    });
    document.getElementById('btn-clear').addEventListener('click', () => {
      out.value = '';
      vscode.postMessage({ type: 'clearHistory' });
    });
    document.getElementById('btn-prev').addEventListener('click', () => {
      vscode.postMessage({ type: 'historyPrev' });
    });
    document.getElementById('btn-next').addEventListener('click', () => {
      vscode.postMessage({ type: 'historyNext' });
    });

    window.addEventListener('message', (event) => {
      const msg = event.data || {};
      // Clear busy overlay on any message that represents completion or error
      if (['analysisResult', 'runnerResult', 'error', 'status'].includes(msg.type)) {
        setBusy(false);
      }
    document.getElementById('btn-run-tests').addEventListener('click', () => {
      setBusy(true);
      vscode.postMessage({ type: 'runTests' });
    });
    document.getElementById('btn-run-cmd').addEventListener('click', () => {
      setBusy(true);
      vscode.postMessage({ type: 'runCommand' });
    });
      if (msg.type === 'status') { log('[status] ' + msg.message); return; }
      if (msg.type === 'error')  { log('[error] '  + msg.message); return; }
      if (msg.type === 'fileContent') {
        out.value = '📄 ' + msg.path + '\\n\\n' + msg.body;
        return;
      }
      if (msg.type === 'fileWritten') {
        out.value = '✅ Wrote ' + msg.path + '\\n\\n' + (msg.body ?? '');
        return;
      }
      if (msg.type === 'analysisResult') {
        const b = msg.body || {};
        const header = [];
        if (b.exception) header.push('Exception: ' + b.exception);
        if (b.file) header.push('Location: ' + b.file);
        const note = b._note || b.note;
        if (note) header.push('Note: ' + note);

        let text = '🧠 Analysis for: ' + (msg.path || '(editor/selection)') + '\\n';
        if (header.length) text += header.map(s => '• ' + s).join('\\n') + '\\n';

        if (b.rca) {
          text += '\\nRCA:\\n' + (typeof b.rca === 'string' ? b.rca : JSON.stringify(b.rca, null, 2)) + '\\n';
        }
        if (Array.isArray(b.context) && b.context.length) {
          text += '\\nContext:\\n' + b.context.map(l => '  ' + l).join('\\n') + '\\n';
        }
        text += '\\n---\\nRaw JSON:\\n' + JSON.stringify(b, null, 2);

        out.value = text;
        return;
      }
      if (msg.type === 'runnerResult') {
        const b = msg.body || {};
        let text = '🧪 Runner Result\\n';
        text += JSON.stringify(b, null, 2);
        out.value = text;
        return;
      }
      log('[unknown message] ' + JSON.stringify(msg));
    });
  </script>
</body>
</html>`;
  }
}

function getNonce(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let s = "";
  for (let i = 0; i < 32; i++) s += chars.charAt(Math.floor(Math.random() * chars.length));
  return s;
}