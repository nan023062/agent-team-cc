// Demo 2：通过 AIAgent + AgentSession 实现多轮对话。
// 验证 AgentSession 能在多轮之间携带上下文，第二次回复可以引用第一次说过的内容。
using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using OpenAI.Chat;
using UnityEditor;
using UnityEngine;

namespace CBIM.Demos.Msai
{
    internal sealed class Demo02_AgentConversation : EditorWindow
    {
        private const string DefaultInstructions =
            "你是一个乐于助人的 Unity 游戏设计助手。回复请控制在 80 字以内。";

        private readonly List<(string role, string text)> _history = new List<(string role, string text)>();
        private string _input = "我在做一个 RPG。";
        private Vector2 _scroll;
        private bool _isRunning;

        private AIAgent _agent;
        private AgentSession _session;
        private string _agentKeyUsed;   // 检测 API key 变化 → 重建 agent

        [MenuItem("CBIM/Demo/02_AgentConversation")]
        private static void Open()
        {
            var w = GetWindow<Demo02_AgentConversation>(true, "Demo 2 — Agent 多轮对话", true);
            w.minSize = new Vector2(600, 480);
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("AIAgent + AgentSession 多轮对话", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox(
                "第一轮会创建 AgentSession，后续轮复用同一个 session。Agent 应当记得之前说过的内容" +
                "（例如先告诉它 '我在做 RPG'，再问它关于敌人设计的问题，它应当结合 RPG 上下文回答）。",
                MessageType.Info);

            if (!ApiKeyReader.RequireKey(ApiKeyReader.OpenAIEnvVar, out var apiKey, out var err))
            {
                ApiKeyReader.DrawMissingKeyWarning(ApiKeyReader.OpenAIEnvVar, err);
                return;
            }

            _scroll = EditorGUILayout.BeginScrollView(_scroll, GUILayout.MinHeight(260));
            foreach (var (role, text) in _history)
            {
                EditorGUILayout.LabelField(role, EditorStyles.boldLabel);
                float w = Mathf.Max(60f, position.width - 30f);
                float h = Mathf.Max(20f, EditorStyles.textArea.CalcHeight(new GUIContent(text ?? ""), w));
                EditorGUILayout.SelectableLabel(text ?? "", EditorStyles.textArea, GUILayout.MinHeight(h));
                EditorGUILayout.Space();
            }
            EditorGUILayout.EndScrollView();

            EditorGUILayout.LabelField("你的消息：");
            _input = EditorGUILayout.TextArea(_input, GUILayout.MinHeight(50));

            EditorGUILayout.BeginHorizontal();
            using (new EditorGUI.DisabledScope(_isRunning || string.IsNullOrWhiteSpace(_input)))
            {
                if (GUILayout.Button(_isRunning ? "发送中…" : "发送"))
                {
                    _ = SendAsync(apiKey, _input);
                }
            }
            if (GUILayout.Button("重置会话"))
            {
                _history.Clear();
                _session = null;
                _agent = null;
                _agentKeyUsed = null;
                Repaint();
            }
            EditorGUILayout.EndHorizontal();
        }

        private async Task SendAsync(string apiKey, string message)
        {
            _isRunning = true;
            _history.Add(("用户", message));
            _input = "";
            Repaint();
            try
            {
                if (_agent == null || _agentKeyUsed != apiKey)
                {
                    ChatClient cc = DemoUtils.NewChatClient(apiKey);
                    _agent = cc.AsAIAgent(instructions: DefaultInstructions, name: "UnityDesignAssistant");
                    _agentKeyUsed = apiKey;
                    _session = await _agent.CreateSessionAsync();
                    Debug.Log("[Demo2] 已创建新的 AgentSession");
                }

                AgentResponse resp = await _agent.RunAsync(message, _session);
                var text = resp.Text;
                _history.Add(("助手", text));
                Debug.Log($"[Demo2] 助手：{text}");
            }
            catch (Exception ex)
            {
                _history.Add(("错误", ex.Message));
                Debug.LogException(ex);
            }
            finally
            {
                _isRunning = false;
                Repaint();
            }
        }
    }
}
