import * as vscode from 'vscode'

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand('cbim.hello', () => {
      vscode.window.showInformationMessage('CBIM v2 — skeleton alive')
    })
  )
}

export function deactivate(): void {}
