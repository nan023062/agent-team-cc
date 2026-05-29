using System;
using System.Collections.Generic;
using System.Linq;
using CBIM.AgentSystem;

namespace CBIM.TaskScheduler
{
    public sealed class CbimTask
    {
        public string TaskId { get; }
        public Agent Who { get; }
        public IReadOnlyList<string> Where { get; }
        public string What { get; }
        public string ParentTaskId { get; }
        public string OriginChannel { get; }
        public IReadOnlyDictionary<string, object> Params { get; }
        public DateTime CreatedAt { get; }

        public CbimTask(
            string TaskId,
            Agent Who,
            IReadOnlyList<string> Where,
            string What,
            string ParentTaskId = null,
            string OriginChannel = null,
            IReadOnlyDictionary<string, object> Params = null,
            DateTime CreatedAt = default)
        {
            this.TaskId = TaskId;
            this.Who = Who;
            this.Where = Where;
            this.What = What;
            this.ParentTaskId = ParentTaskId;
            this.OriginChannel = OriginChannel;
            this.Params = Params;
            this.CreatedAt = CreatedAt;
        }

        public static CbimTask Create(
            Agent who,
            IEnumerable<string> where,
            string what,
            string parentTaskId = null,
            string originChannel = null,
            IDictionary<string, object> @params = null)
        {
            if (who is null) throw new ArgumentNullException(nameof(who));
            if (where is null) throw new ArgumentNullException(nameof(where));
            if (string.IsNullOrWhiteSpace(what)) throw new ArgumentException("what must be non-empty.", nameof(what));

            return new CbimTask(
                TaskId: Guid.NewGuid().ToString("N"),
                Who: who,
                Where: where.ToList().AsReadOnly(),
                What: what,
                ParentTaskId: parentTaskId,
                OriginChannel: originChannel,
                Params: @params is null ? null : new Dictionary<string, object>(@params),
                CreatedAt: DateTime.UtcNow);
        }
    }
}
