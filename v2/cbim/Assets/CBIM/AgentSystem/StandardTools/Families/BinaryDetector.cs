using System.Text;

namespace CBIM.AgentSystem.StandardTools
{
    // 启发式的二进制/文本判别器。作用于文件前 N 个字节
    //（N 由调用方决定，通常 8 KB）。
    //
    // 规则（按顺序）：
    //   1. 空缓冲 → 文本。
    //   2. 出现 NUL 字节 → 二进制。NUL 在 UTF-8 / UTF-16 文本里非法，
    //      但在编译产物里随处可见。
    //   3. 带 UTF-8/16 BOM → 文本。
    //   4. 超过 30% 的字节落在可打印 ASCII + 常用控制字符（TAB / LF / CR）之外 → 二进制。
    //
    // 故意做得很轻量；需要精确 MIME 识别的 agent 应调用专门的库。
    public static class BinaryDetector
    {
        public static bool IsBinary(byte[] head)
        {
            if (head == null || head.Length == 0)
            {
                return false;
            }

            if (HasBom(head))
            {
                return false;
            }

            int suspicious = 0;
            for (int i = 0; i < head.Length; i++)
            {
                byte b = head[i];
                if (b == 0x00)
                {
                    return true;
                }
                if (b == 0x09 || b == 0x0A || b == 0x0D)
                {
                    continue;
                }
                if (b < 0x20)
                {
                    suspicious++;
                }
                else if (b == 0x7F)
                {
                    suspicious++;
                }
            }

            double ratio = (double)suspicious / head.Length;
            return ratio > 0.30;
        }

        private static bool HasBom(byte[] head)
        {
            if (head.Length >= 3 &&
                head[0] == 0xEF && head[1] == 0xBB && head[2] == 0xBF)
            {
                return true;
            }
            if (head.Length >= 2 &&
                ((head[0] == 0xFF && head[1] == 0xFE) ||
                 (head[0] == 0xFE && head[1] == 0xFF)))
            {
                return true;
            }
            return false;
        }
    }
}
