using System.Collections.Generic;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using UnityEditor;
using UnityEngine;

namespace CBIM.VerifyMsai
{
    /// <summary>
    /// Microsoft.Extensions.AI + Microsoft.Agents.AI DLL 接入的冒烟测试。
    /// 菜单：CBIM/Verify/MsExtensionsAI
    /// 验证两层：
    ///   1. IChatClient（Microsoft.Extensions.AI）——底层 chat 调用。
    ///   2. AIAgent（Microsoft.Agents.AI）——包裹同一个 IChatClient 的高层 agent。
    /// </summary>
    internal sealed class VerifyWindow : EditorWindow
    {
        private string _chatClientResult = "(not run yet)";
        private string _agentResult = "(not run yet)";

        [MenuItem("CBIM/Verify/MsExtensionsAI")]
        private static void Open()
        {
            var w = GetWindow<VerifyWindow>(true, "Verify MsExtensionsAI", true);
            w.minSize = new Vector2(480, 220);
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("Microsoft.Extensions.AI + Microsoft.Agents.AI smoke test", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox(
                "Click 'Run' to:\n" +
                "  1) construct a MockChatClient and call GetResponseAsync (IChatClient layer)\n" +
                "  2) wrap that same MockChatClient as an AIAgent and call RunAsync (AIAgent layer)\n" +
                "If DLLs resolve correctly both lines below show 'hello from mock'.",
                MessageType.Info);

            if (GUILayout.Button("Run"))
            {
                RunAsync();
            }

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("IChatClient result:", EditorStyles.boldLabel);
            EditorGUILayout.SelectableLabel(_chatClientResult, GUILayout.Height(30));
            EditorGUILayout.LabelField("AIAgent result:", EditorStyles.boldLabel);
            EditorGUILayout.SelectableLabel(_agentResult, GUILayout.Height(30));
        }

        private async void RunAsync()
        {
            // 第一层 —— IChatClient
            try
            {
                using var client = new MockChatClient();
                var messages = new List<ChatMessage>
                {
                    new ChatMessage(ChatRole.User, "ping")
                };
                var resp = await client.GetResponseAsync(messages);
                _chatClientResult = resp.Messages.Count > 0 ? resp.Messages[0].Text : "(empty)";
                Debug.Log($"[VerifyMsai][IChatClient] {_chatClientResult}");
                Repaint();
            }
            catch (System.Exception ex)
            {
                _chatClientResult = "ERROR: " + ex.Message;
                Debug.LogException(ex);
                Repaint();
            }

            // 第二层 —— AIAgent（Microsoft.Agents.AI）
            try
            {
                using var client = new MockChatClient();
                AIAgent agent = client.AsAIAgent();
                AgentResponse runResp = await agent.RunAsync("hello");
                _agentResult = runResp.Text ?? "(empty)";
                Debug.Log($"[VerifyMsai][AIAgent] {_agentResult}");
                Repaint();
            }
            catch (System.Exception ex)
            {
                _agentResult = "ERROR: " + ex.Message;
                Debug.LogException(ex);
                Repaint();
            }
        }
    }
}
