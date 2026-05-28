using System.Collections.Generic;

namespace CBIM.Skills
{
    /// <summary>
    /// 技能配置仓储抽象。
    ///
    /// Skill 是「配置类资产」——纯文本描述符，可被作者本地维护，
    /// 也可统一在云端集中管理后下发各 Agent。本接口屏蔽后端差异，
    /// 让能力侧 / 业务侧（Agent.Skills / Module.Workflows）共用同一查询面。
    ///
    /// 设计要点：
    ///   - 同步方法——本模块不引入 Task / async（与 CBIM.Storage 一致）。
    ///     云后端如需异步，由 Agent / Workspace 装配侧自己包装。
    ///   - 描述符不可变——<see cref="Put"/> 替换整条记录，不支持 in-place 字段更新。
    ///   - <see cref="Query"/> 是可选能力——本地后端可只做最简子串匹配；
    ///     接 Pinecone / Weaviate 时再做向量检索。
    /// </summary>
    public interface ISkillStore
    {
        /// <summary>按 Id 取一条技能描述符。找不到返回 null。</summary>
        SkillDescriptor Get(string id);

        /// <summary>当前后端全量快照。</summary>
        IReadOnlyList<SkillDescriptor> List();

        /// <summary>
        /// 简单文本检索——后端可选实现，默认最多返回 <paramref name="topK"/> 条。
        /// 本地后端做忽略大小写的子串匹配；空查询 / 非正 topK 返回空集合。
        /// </summary>
        IReadOnlyList<SkillDescriptor> Query(string text, int topK);

        /// <summary>按 Id upsert——存在则替换整条记录，不存在则新增。</summary>
        void Put(SkillDescriptor descriptor);

        /// <summary>按 Id 删除一条记录。不存在返回 false。</summary>
        bool Delete(string id);
    }
}
