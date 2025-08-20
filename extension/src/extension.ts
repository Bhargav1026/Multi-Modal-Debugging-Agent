import * as vscode from "vscode";

export function activate(context: vscode.ExtensionContext) {
  const disposable = vscode.commands.registerCommand(
    "multiModalDebug.helloWorld",
    () => vscode.window.showInformationMessage("Multi-Modal Debugging Agent Extension Running 🚀")
  );
  context.subscriptions.push(disposable);
}

export function deactivate() {}