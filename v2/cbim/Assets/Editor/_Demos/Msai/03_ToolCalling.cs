// Demo 3：自动 tool calling。
// 验证 ChatClientAgent 自动注入的 FunctionInvokingChatClient 循环
// 能调用 C# 方法、把结果回喂给模型，并产出最终自然语言回答。
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Threading.Tasks;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using OpenAI.Chat;
using UnityEditor;
using UnityEngine;

namespace CBIM.Demos.Msai
{
    internal sealed class Demo03_ToolCalling : EditorWindow
    {
        private string _prompt = "现在几点？然后帮我掷一个 d20，把点数告诉我。";
        private readonly List<string> _toolLog = new List<string>();
        private string _final = "（尚未运行）";
        private Vector2 _scroll;
        private bool _isRunning;

        [MenuItem("CBIM/Demo/03_ToolCalling")]
        private static void Open()
        {
            var w = GetWindow<Demo03_ToolCalling>(true, "Demo 3 — Tool 调用", true);
            w.minSize = new Vector2(600, 460);
        }

        // ---- 暴露给模型的工具 ----
        // 两个工具都通过下面的 AIFunctionFactory.Create 包装。描述来自
        // [Description] 特性 —— 这就是 LLM 在 tool schema 里看到的内容。

        [Description("获取当前本地日期时间的字符串。")]
        private static string GetCurrentTime()
        {
            var v = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            Debug.Log($"[Demo3][tool] GetCurrentTime() -> {v}");
            return v;
        }

        [Description("掷一个骰子并返回点数。")]
        private static int RollDice(
            [Description("骰子面数，默认为 6。")] int sides = 6)
        {
            if (sides < 2) sides = 2;
            var v = UnityEngine.Random.Range(1, sides + 1);
            Debug.Log($"[Demo3][tool] RollDice(sides={sides}) -> {v}");
            return v;
        }

        // ---- UI ----

        private void OnGUI()
        {
            EditorGUILayout.LabelField("带自动 tool 调用的 AIAgent", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox(
                "两个 C# 方法以工具形式暴露给模型（GetCurrentTime、RollDice）。Agent 的自动函数调用循环" +
                "应当按需调用它们，并产出最终的自然语言回答。",
                MessageType.Info);

            if (!ApiKeyReader.RequireKey(ApiKeyReader.OpenAIEnvVar, out var apiKey, out var err))
            {
                ApiKeyReader.DrawMissingKeyWarning(ApiKeyReader.OpenAIEnvVar, err);
                return;
            }

            EditorGUILayout.LabelField("提示词：");
            _prompt = EditorGUILayout.TextArea(_prompt, GUILayout.MinHeight(50));

            using (new EditorGUI.DisabledScope(_isRunning || string.IsNullOrWhiteSpace(_prompt)))
            {
                if (GUILayout.Button(_isRunning ? "发送中…" : "发送"))
                {
                    _ = RunAsync(apiKey, _prompt);
                }
            }

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("工具调用日志（也可看 Console）：", EditorStyles.boldLabel);
            _scroll = EditorGUILayout.BeginScrollView(_scroll, GUILayout.MinHeight(120));
            foreach (var line in _toolLog) EditorGUILayout.SelectableLabel(line, GUILayout.Height(18));
            EditorGUILayout.EndScrollView();

            EditorGUILayout.LabelField("最终回答：", EditorStyles.boldLabel);
            EditorGUILayout.SelectableLabel(_final, EditorStyles.textArea, GUILayout.MinHeight(80));
        }

        private async Task RunAsync(string apiKey, string prompt)
        {
            _isRunning = true;
            _toolLog.Clear();
            _final = "（发送中…）";
            Repaint();
            try
            {
                var tools = new List<AITool>
                {
                    AIFunctionFactory.Create((Func<string>)GetCurrentTime),
                    AIFunctionFactory.Create((Func<int, int>)RollDice),
                };

                ChatClient cc = DemoUtils.NewChatClient(apiKey);
                // 当带 tools 时，ChatClientAgent 会自动插入 FunctionInvokingChatClient ——
                // 不需要手工挂中间件。
                AIAgent agent = cc.AsAIAgent(
                    instructions: "请使用提供的工具来回答用户。" +
                                  "如果工具给了你一个数字，请在回复中包含这个准确数字。",
                    name: "ToolDemoAgent",
                    tools: tools);

                AgentResponse resp = await agent.RunAsync(prompt);

                // 遍历响应里的每条消息 —— 函数调用 / 调用结果以
                // FunctionCallContent / FunctionResultContent 形式出现在消息内容里。
                foreach (var msg in resp.Messages)
                {
                    foreach (var content in msg.Contents)
                    {
                        switch (content)
                        {
                            case FunctionCallContent fc:
                                _toolLog.Add($"[call] {fc.Name}({SerializeArgs(fc.Arguments as System.Collections.IEnumerable)})");
                                break;
                            case FunctionResultContent fr:
                                _toolLog.Add($"[result] {fr.CallId} -> {fr.Result}");
                                break;
                        }
                    }
                }

                _final = resp.Text;
                Debug.Log($"[Demo3] 最终回答：{_final}");
            }
            catch (Exception ex)
            {
                _final = "错误：" + ex.Message;
                Debug.LogException(ex);
            }
            finally
            {
                _isRunning = false;
                Repaint();
            }
        }

        private static string SerializeArgs(System.Collections.IEnumerable args)
        {
            if (args == null) return "";
            var parts = new List<string>();
            foreach (var entry in args)
            {
                // 不论字典具体类型如何，每个 entry 都是 KeyValuePair<string, object?>。
                var t = entry.GetType();
                var key = t.GetProperty("Key")?.GetValue(entry);
                var val = t.GetProperty("Value")?.GetValue(entry);
                parts.Add($"{key}={val}");
            }
            return string.Join(", ", parts);
        }
    }
}
