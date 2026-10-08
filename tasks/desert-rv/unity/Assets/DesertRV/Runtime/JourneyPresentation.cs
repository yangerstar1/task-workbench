namespace DesertRV
{
    public static class JourneyPresentation
    {
        public static string Objective(SessionState state, PoweredEncounterState encounter)
        {
            if (state.Status == SessionStatus.Completed) return "信标已启动，房车抵达安全区 · 整局胜利";
            if (state.SceneId == 1) return (state.Upgrades & VehicleUpgrades.Ram) != 0 ? "驾驶房车撞开路障，驶向废料场" : state.HasPart(ComponentPart.RamPart) ? "回车安装撞角" : "搜索加油站的撞角组件";
            if (state.SceneId == 2 && (state.Upgrades & VehicleUpgrades.Arc) != 0) return "拔除电缆，驾驶房车前往信标";
            if (state.SceneId == 2 && encounter != null && encounter.Complete) return state.HasPart(ComponentPart.Coil) ? "回车安装电弧线圈" : "取回已解锁的线圈";
            if (state.SceneId == 3 && encounter != null && encounter.Complete) return "拔除电缆，驾驶房车驶入安全区";
            if (!state.PowerConnected) return "停车下车，连接房车电源";
            return encounter == null ? "检查地区绑定" : $"守住供电设备 · 第 {encounter.CurrentWave} 波 · 充能 {encounter.ChargeProgress:P0}";
        }
    }
}
