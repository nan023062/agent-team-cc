using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using CBIM.AgentSystem;

// Alias 消歧——CBIM.AgentSystem 既是 namespace 又是 class。本文件用 `AgentSystemService`
// 引用类型，避免 `AgentSystem.AgentSystem` 这种重复名段写法。
using AgentSystemService = CBIM.AgentSystem.AgentSystem;
using AgentInstance = CBIM.AgentSystem.Agent;

namespace CBIM.Channel
{
    /// <summary>
    /// Channel 注册表 + 生命周期管理服务——CBIM 入口层的总入口。
    ///
    /// <para>职责（仅四件事）：</para>
    /// <list type="number">
    ///   <item><see cref="OpenChannelAsync"/>——按 AgentDescription 装配 Agent 实例（委托 <see cref="AgentSystem"/>），包成 Channel 并注册。</item>
    ///   <item><see cref="GetChannel"/>——按 ID 查活动 Channel。</item>
    ///   <item><see cref="ListChannels"/>——列出全部活动 Channel。</item>
    ///   <item><see cref="CloseChannelAsync"/>——注销 Channel + 释放底层 Agent。</item>
    /// </list>
    ///
    /// <para><b>薄封装铁律</b>：本服务不直接 new ChatClientAgent / 不感知脑区 /
    /// 不写 Session 日志——所有装配 / 脑区编织 / Memory 桥接均由 <see cref="AgentSystem"/>
    /// 在 OpenInstanceAsync 内完成。Channel 层只做「ID ↔ Channel 实例」的轻量映射。</para>
    ///
    /// <para>线程安全：内部 <c>_channels</c> 字典所有读写均在 <c>_lock</c> 锁内——
    /// Unity 主线程 + 后台 async 路径并发安全。</para>
    /// </summary>
    public sealed class ChannelService
    {
        private readonly AgentSystemService _agentSystem;
        private readonly Dictionary<string, Channel> _channels = new Dictionary<string, Channel>(StringComparer.Ordinal);
        private readonly object _lock = new object();

        public ChannelService(AgentSystemService agentSystem)
        {
            if (agentSystem == null)
                throw new ArgumentNullException(nameof(agentSystem));
            _agentSystem = agentSystem;
        }

        /// <summary>
        /// 按 AgentDescription 装配一个 Agent 实例并包成 Channel——一次开通对话窗口。
        ///
        /// <para>步骤：</para>
        /// <list type="number">
        ///   <item>校验 <see cref="ChannelOptions.WorkspaceRoot"/> 非空白
        ///   （MCP server / ExternalMotorCortex subprocess 工作目录必填）。</item>
        ///   <item>调 <c>_agentSystem.OpenInstanceAsync</c> 装配 Agent（透传 WorkspaceRoot 为 TaskWhere）。</item>
        ///   <item>生成 Guid 作 ChannelId。</item>
        ///   <item>构造 Channel（持 instance.Prefrontal.Agent 句柄）。</item>
        ///   <item>注册到 <c>_channels</c> 字典。</item>
        ///   <item>返回 Channel。</item>
        /// </list>
        ///
        /// <para>失败处理：<c>OpenInstanceAsync</c> 抛异常时（如 BrainConfig 校验失败 /
        /// FileBackend 未注入），本方法不吞——直接向上传播，Channel 不注册半装态。</para>
        /// </summary>
        public async Task<Channel> OpenChannelAsync(string agentDescriptionId, ChannelOptions options)
        {
            if (string.IsNullOrWhiteSpace(agentDescriptionId))
                throw new ArgumentException("agentDescriptionId 不能为空", nameof(agentDescriptionId));
            if (options == null)
                throw new ArgumentNullException(nameof(options));
            if (string.IsNullOrWhiteSpace(options.WorkspaceRoot))
                throw new ArgumentException(
                    "ChannelOptions.WorkspaceRoot 不能为空——MCP server 启动 / ExternalMotorCortex " +
                    "subprocess 工作目录均以此为锚。",
                    nameof(options));

            var openOptions = new OpenInstanceOptions
            {
                TaskWhere = options.WorkspaceRoot,
                ActivatedByTaskId = options.ActivatedByTaskId,
            };

            AgentInstance instance = await _agentSystem
                .OpenInstanceAsync(agentDescriptionId, openOptions)
                .ConfigureAwait(false);

            string channelId = Guid.NewGuid().ToString();
            var channel = new Channel(channelId, instance);

            lock (_lock)
            {
                _channels[channelId] = channel;
            }

            return channel;
        }

        /// <summary>按 ID 查活动 Channel。找不到返 null。</summary>
        public Channel GetChannel(string channelId)
        {
            if (string.IsNullOrWhiteSpace(channelId)) return null;
            lock (_lock)
            {
                return _channels.TryGetValue(channelId, out var c) ? c : null;
            }
        }

        /// <summary>列出当前全部活动 Channel——快照拷贝，调用方修改返回列表不影响内部状态。</summary>
        public IReadOnlyList<Channel> ListChannels()
        {
            lock (_lock)
            {
                return new List<Channel>(_channels.Values);
            }
        }

        /// <summary>
        /// 关闭 Channel——从注册表移除并归还底层 Agent 实例（触发 <c>AgentSystem.CloseInstanceAsync</c>
        /// → <c>Agent.DisposeAsync</c> 按 MotorCortex → 其他脑区 → Prefrontal → Memory → McpHandles → Session
        /// 顺序释放）。
        ///
        /// <para>幂等：未知 channelId 静默返回（已被关闭或从未注册）；
        /// 同一 channelId 多次调用安全。</para>
        /// </summary>
        public async Task CloseChannelAsync(string channelId)
        {
            if (string.IsNullOrWhiteSpace(channelId)) return;

            Channel channel;
            lock (_lock)
            {
                if (!_channels.TryGetValue(channelId, out channel)) return;
                _channels.Remove(channelId);
            }

            // 锁外执行 await——CloseInstanceAsync 内部还有 DisposeAsync 的串行释放，
            // 锁内 await 会无谓拖慢其他 Channel 操作。
            await _agentSystem.CloseInstanceAsync(channel.Instance).ConfigureAwait(false);
        }
    }
}
