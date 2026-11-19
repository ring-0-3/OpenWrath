using System;

namespace BinaryAssetBuilder.Utility
{
    internal sealed class AssetHandle : IComparable<AssetHandle>, IComparable
    {
        private readonly uint _instanceId;
        private readonly uint _typeId;

        public uint InstanceId => _instanceId;
        public uint TypeId => _typeId;

        // Needed so SortedDictionary<AssetHandle,...> (used for base-patch-stream asset lookup) works.
        public int CompareTo(AssetHandle other)
        {
            if (other is null) { return 1; }
            int c = _typeId.CompareTo(other._typeId);
            return c != 0 ? c : _instanceId.CompareTo(other._instanceId);
        }

        public int CompareTo(object obj) => obj is AssetHandle o ? CompareTo(o) : 1;

        public AssetHandle()
        {
        }

        public AssetHandle(uint typeId, uint instanceId)
        {
            _typeId = typeId;
            _instanceId = instanceId;
        }

        public AssetHandle(AssetHandle src)
        {
            _instanceId = src._instanceId;
            _typeId = src._typeId;
        }

        public override bool Equals(object obj)
        {
            return obj is AssetHandle objT && _instanceId == objT._instanceId && _typeId == objT._typeId;
        }

        public override int GetHashCode()
        {
            return (int)_instanceId ^ (int)_typeId;
        }
    }
}
