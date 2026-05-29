namespace CBIM.AgentSystem.Kernel.Neuron
{
    /// <summary>
    /// 神经元引擎种别——供 Brain 层做能力体征判断（如「External 不可作为主脑」）。
    /// 用枚举而非运行期类型判别，让未来追加新 NeuronKind 不破坏现有校验代码。
    /// </summary>
    public enum NeuronKind
    {
        /// <summary>Microsoft.Agents.AI（msai）装配的标准神经元——走 ChatClientAgent + FunctionInvokingChatClient。</summary>
        Msai,

        /// <summary>外部引擎桥接神经元——走 IExternalEngineAdapter（如 Claude Code）。</summary>
        External,
    }
}
