using System.IO;
using UnityEngine;
using CBIM.Storage;

namespace CBIM.UnityHost
{
    /// <summary>
    /// Unity 场景侧的 CBIM 启动器。把 Unity 的 Application.persistentDataPath
    /// 拼成 .cbim/ 根目录，构造 FileBackend 实例。
    ///
    /// CBIM 本身不依赖 Unity——这个适配层是唯一的 Unity 接缝。
    /// </summary>
    public static class CbimBootstrap
    {
        /// <summary>
        /// 用 Unity 标准持久化路径构造 FileBackend。
        /// 等价于 new FileBackend(Application.persistentDataPath + "/.cbim").
        /// </summary>
        public static FileBackend CreateStorage()
        {
            string root = Path.Combine(Application.persistentDataPath, ".cbim");
            return new FileBackend(root);
        }
    }
}
