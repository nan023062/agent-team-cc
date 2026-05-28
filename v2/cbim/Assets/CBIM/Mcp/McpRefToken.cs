using System;

namespace CBIM.Mcp
{
    /// <summary>
    /// Opaque reference token for an MCP instance, issued by the manager.
    /// <para>
    /// The token packs a reusable slot index (<see cref="InstanceId"/>) in the
    /// high 32 bits and a monotonically incrementing generation
    /// (<see cref="Gen"/>) in the low 32 bits of <see cref="Raw"/>. The
    /// generation guards against ABA — when a slot is recycled, the new
    /// occupant gets a fresh generation, so stale tokens fail equality checks
    /// instead of silently aliasing onto the wrong instance.
    /// </para>
    /// <para>
    /// Treat the token as opaque: never derive identity from the slot alone,
    /// and always resolve it through the manager that issued it.
    /// </para>
    /// </summary>
    public readonly struct McpRefToken : IEquatable<McpRefToken>
    {
        /// <summary>
        /// Raw 64-bit encoding: <c>(slot &lt;&lt; 32) | gen</c>. Exposed for
        /// serialization and interop; prefer <see cref="InstanceId"/> /
        /// <see cref="Gen"/> for logic.
        /// </summary>
        public readonly long Raw;

        /// <summary>
        /// Reusable slot index identifying the manager's internal storage cell.
        /// Slot values are recycled across instance lifetimes; pair with
        /// <see cref="Gen"/> for unique identity.
        /// </summary>
        public int InstanceId => (int)(Raw >> 32);

        /// <summary>
        /// Generation counter for ABA protection. Incremented every time the
        /// slot at <see cref="InstanceId"/> is reassigned, so a stale token
        /// from a previous occupant compares unequal to the current one.
        /// </summary>
        public int Gen => (int)Raw;

        /// <summary>
        /// Reconstructs a token from its component parts.
        /// <para>
        /// Intended for test scenarios that need to forge a specific
        /// (slot, gen) pair. Production code must obtain tokens from
        /// <c>McpManager.Request</c> — never fabricate them.
        /// </para>
        /// </summary>
        public McpRefToken(int instanceId, int gen)
            => Raw = ((long)instanceId << 32) | (uint)gen;

        internal McpRefToken(long raw) { Raw = raw; }

        public bool Equals(McpRefToken other) => Raw == other.Raw;
        public override bool Equals(object obj) => obj is McpRefToken t && Equals(t);
        public override int GetHashCode() => Raw.GetHashCode();

        /// <summary>
        /// Debug format: <c>#{slot}.{gen}</c>. Used by log lines that need
        /// to disambiguate two tokens sharing the same slot.
        /// </summary>
        public override string ToString() => $"#{InstanceId}.{Gen}";

        public static bool operator ==(McpRefToken a, McpRefToken b) => a.Raw == b.Raw;
        public static bool operator !=(McpRefToken a, McpRefToken b) => a.Raw != b.Raw;
    }
}
