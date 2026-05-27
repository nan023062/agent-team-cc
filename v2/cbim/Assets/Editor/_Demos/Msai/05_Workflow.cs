// Demo 5：多 agent workflow。
// 验证 Microsoft.Agents.AI.Workflows 能把两个 AIAgent 串成 executor，
// 把前一个 agent 的输出消息传给后一个 agent。
using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Microsoft.Agents.AI;
using Microsoft.Agents.AI.Workflows;
using Microsoft.Extensions.AI;
using OpenAI.Chat;
using ChatMessage = Microsoft.Extensions.AI.ChatMessage;
using UnityEditor;
using UnityEngine;

namespace CBIM.Demos.Msai
{
    internal sealed class Demo05_Workflow : EditorWindow
    {
        private string _input = "Unity 里怎么烘焙光照贴图？";
        private readonly List<string> _eventLog = new List<string>();
        private Vector2 _scroll;
        private bool _isRunning;

        [MenuItem("CBIM/Demo/05_Workflow")]
        private static void Open()
        {
            var w = GetWindow<Demo05_Workflow>(true, "Demo 5 — Workflow 编排", true);
            w.minSize = new Vector2(680, 520);
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("两 agent workflow：分类器 → 回答器", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox(
                "ClassifierAgent 读取用户输入并输出一个标签（question / command / chat）。\n" +
                "ResponderAgent 接收整段对话（用户消息 + 分类器标签）并写出最终回复。\n" +
                "看下方事件日志可以看到两个 agent 的流式输出。",
                MessageType.Info);

            if (!ApiKeyReader.RequireKey(ApiKeyReader.OpenAIEnvVar, out var apiKey, out var err))
            {
                ApiKeyReader.DrawMissingKeyWarning(ApiKeyReader.OpenAIEnvVar, err);
                return;
            }

            EditorGUILayout.LabelField("用户输入：");
            _input = EditorGUILayout.TextArea(_input, GUILayout.MinHeight(50));

            using (new EditorGUI.DisabledScope(_isRunning || string.IsNullOrWhiteSpace(_input)))
            {
                if (GUILayout.Button(_isRunning ? "运行中…" : "运行 workflow"))
                {
                    _ = RunAsync(apiKey, _input);
                }
            }

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Workflow 事件：", EditorStyles.boldLabel);
            _scroll = EditorGUILayout.BeginScrollView(_scroll, GUILayout.MinHeight(280));
            foreach (var line in _eventLog) EditorGUILayout.SelectableLabel(line, GUILayout.Height(18));
            EditorGUILayout.EndScrollView();
        }

        private async Task RunAsync(string apiKey, string userInput)
        {
            _isRunning = true;
            _eventLog.Clear();
            Repaint();
            try
            {
                ChatClient cc = DemoUtils.NewChatClient(apiKey);

                AIAgent classifier = cc.AsAIAgent(
                    name: "Classifier",
                    instructions:
                        "你是一个严格的分类器。读取最新的用户消息，只回复一个" +
                        "小写英文单词，从以下三选一：question、command、chat。不要标点，不要解释。");

                AIAgent responder = cc.AsAIAgent(
                    name: "Responder",
                    instructions:
                        "你会收到一段对话，包含用户的原始消息，以及来自分类器的一条助手消息" +
                        "（单个英文单词：question / command / chat）。" +
                        "根据分类器标签来确定语气：\n" +
                        "  question -> 用事实简洁回答\n" +
                        "  command -> 先确认收到，然后列出步骤\n" +
                        "  chat -> 用 1–2 句话温和地回复\n" +
                        "然后写出给用户的最终回复。开头加上标签 '[label=<分类标签>]'。");

                var workflow = new WorkflowBuilder(classifier)
                    .AddEdge(classifier, responder)
                    .Build();

                await using StreamingRun run = await InProcessExecution.RunStreamingAsync(
                    workflow,
                    new ChatMessage(ChatRole.User, userInput));

                // 被包装为 executor 的 agent 会把消息缓存到看见 TurnToken 为止。
                await run.TrySendMessageAsync(new TurnToken(emitEvents: true));

                await foreach (WorkflowEvent evt in run.WatchStreamAsync())
                {
                    switch (evt)
                    {
                        case AgentResponseUpdateEvent update:
                            // 来自其中一个 agent 的流式分片。
                            var text = update.Update?.Text;
                            if (!string.IsNullOrEmpty(text))
                            {
                                _eventLog.Add($"[{update.ExecutorId}] {text}");
                                Repaint();
                            }
                            break;
                        case ExecutorCompletedEvent done:
                            _eventLog.Add($"[done] {done.ExecutorId}");
                            Debug.Log($"[Demo5][done] {done.ExecutorId}");
                            Repaint();
                            break;
                        case WorkflowErrorEvent wfErr:
                            _eventLog.Add("[workflow-error] " + (wfErr.Exception?.Message ?? "unknown"));
                            if (wfErr.Exception != null) Debug.LogException(wfErr.Exception);
                            break;
                        case ExecutorFailedEvent exFail:
                            _eventLog.Add($"[executor-failed] {exFail.ExecutorId} :: {exFail.Data}");
                            Debug.LogError($"[Demo5] executor {exFail.ExecutorId} 失败：{exFail.Data}");
                            break;
                    }
                }

                _eventLog.Add("[workflow complete]");
                Debug.Log("[Demo5] workflow 完成");
            }
            catch (Exception ex)
            {
                _eventLog.Add("错误：" + ex.Message);
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
