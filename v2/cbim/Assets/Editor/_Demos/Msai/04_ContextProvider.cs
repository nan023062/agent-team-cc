// Demo 4：AIContextProvider，在每次 agent 运行前注入额外指令。
// 验证通过 ChatClientAgentOptions.AIContextProviders 挂上的自定义 AIContextProvider
// 能传到模型并改变其行为。
using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using OpenAI.Chat;
using UnityEditor;
using UnityEngine;

namespace CBIM.Demos.Msai
{
    /// <summary>
    /// 一个假装是 workspace 巡视员的 provider。在真实 CBIM 里它会读取 .dna / 源码。
    /// </summary>
    internal sealed class FakeWorkspaceContextProvider : AIContextProvider
    {
        protected override ValueTask<AIContext> ProvideAIContextAsync(
            InvokingContext context, CancellationToken cancellationToken = default)
        {
            var ctx = new AIContext
            {
                Instructions =
                    "当前项目上下文（由 FakeWorkspaceContextProvider 注入）：\n" +
                    "- 引擎：Unity 2020.3\n" +
                    "- 类型：黑暗奇幻 RPG\n" +
                    "- 当前模块：战斗系统\n" +
                    "- 已知技术债：AI 寻路需要重构\n" +
                    "在被要求给建议时，请给出能引用以上事实的具体建议。"
            };
            Debug.Log("[Demo4][provider] 已注入 workspace 上下文");
            return new ValueTask<AIContext>(ctx);
        }
    }

    internal sealed class Demo04_ContextProvider : EditorWindow
    {
        private string _prompt = "我接下来该做什么？";
        private string _plainResult = "（尚未运行）";
        private string _enrichedResult = "（尚未运行）";
        private bool _isRunning;
        private Vector2 _scroll;

        [MenuItem("CBIM/Demo/04_ContextProvider")]
        private static void Open()
        {
            var w = GetWindow<Demo04_ContextProvider>(true, "Demo 4 — 上下文 Provider", true);
            w.minSize = new Vector2(640, 520);
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("AIContextProvider 注入对比", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox(
                "两个 agent，同一个提示词：\n" +
                "  • 朴素 agent → 不挂 provider，预期是泛泛建议\n" +
                "  • 增强 agent → 挂上 FakeWorkspaceContextProvider，应当提到 黑暗奇幻 / 寻路 等关键词\n" +
                "对比两边输出可以看到 provider 的作用。",
                MessageType.Info);

            if (!ApiKeyReader.RequireKey(ApiKeyReader.OpenAIEnvVar, out var apiKey, out var err))
            {
                ApiKeyReader.DrawMissingKeyWarning(ApiKeyReader.OpenAIEnvVar, err);
                return;
            }

            EditorGUILayout.LabelField("提示词：");
            _prompt = EditorGUILayout.TextArea(_prompt, GUILayout.MinHeight(50));

            EditorGUILayout.BeginHorizontal();
            using (new EditorGUI.DisabledScope(_isRunning))
            {
                if (GUILayout.Button("发送（不带上下文）")) _ = SendAsync(apiKey, _prompt, withProvider: false);
                if (GUILayout.Button("发送（带 workspace 上下文）")) _ = SendAsync(apiKey, _prompt, withProvider: true);
                if (GUILayout.Button("两个都发"))
                {
                    _ = SendBothAsync(apiKey, _prompt);
                }
            }
            EditorGUILayout.EndHorizontal();

            _scroll = EditorGUILayout.BeginScrollView(_scroll);
            EditorGUILayout.LabelField("朴素 agent（无 provider）：", EditorStyles.boldLabel);
            EditorGUILayout.SelectableLabel(_plainResult, EditorStyles.textArea, GUILayout.MinHeight(120));
            EditorGUILayout.Space();
            EditorGUILayout.LabelField("增强 agent（带 workspace provider）：", EditorStyles.boldLabel);
            EditorGUILayout.SelectableLabel(_enrichedResult, EditorStyles.textArea, GUILayout.MinHeight(120));
            EditorGUILayout.EndScrollView();
        }

        private async Task SendBothAsync(string apiKey, string prompt)
        {
            await SendAsync(apiKey, prompt, withProvider: false);
            await SendAsync(apiKey, prompt, withProvider: true);
        }

        private async Task SendAsync(string apiKey, string prompt, bool withProvider)
        {
            _isRunning = true;
            if (withProvider) _enrichedResult = "（发送中…）"; else _plainResult = "（发送中…）";
            Repaint();
            try
            {
                ChatClient cc = DemoUtils.NewChatClient(apiKey);

                ChatClientAgentOptions options = new ChatClientAgentOptions
                {
                    Name = withProvider ? "EnrichedAgent" : "PlainAgent",
                    ChatOptions = new ChatOptions
                    {
                        Instructions = "你是一位资深游戏开发导师。请用不超过 80 字给出一条具体建议。",
                    },
                    AIContextProviders = withProvider
                        ? new AIContextProvider[] { new FakeWorkspaceContextProvider() }
                        : null,
                };

                AIAgent agent = cc.AsAIAgent(options);
                AgentResponse resp = await agent.RunAsync(prompt);

                if (withProvider)
                {
                    _enrichedResult = resp.Text;
                    Debug.Log($"[Demo4][enriched] {resp.Text}");
                }
                else
                {
                    _plainResult = resp.Text;
                    Debug.Log($"[Demo4][plain] {resp.Text}");
                }
            }
            catch (Exception ex)
            {
                if (withProvider) _enrichedResult = "错误：" + ex.Message;
                else _plainResult = "错误：" + ex.Message;
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
