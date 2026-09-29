using System;
using System.Collections.Generic;
using ShipRobot.Navigation;
using UnityEngine;

namespace ShipRobot.EquipmentMonitoring
{
    // Opts the existing robot demo into external mission control, never the trainer.
    public sealed class RobotDashboardIntegration : MonoBehaviour
    {
        private NavigationCoordinator navigation;
        private CsvReplayDataSource a, b;
        private EquipmentNetworkBridge bridge;
        private bool started;
        private readonly string sessionId = Guid.NewGuid().ToString("N");
        private readonly List<object> inspections = new List<object>();

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Install()
        {
            var scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
            if (scene.name != "jetbot_env" && scene.name != "EquipmentInspectionDemo") return;
            var nav = FindAnyObjectByType<NavigationCoordinator>();
            if (nav == null || nav.IsTrainingMission || nav.GetComponent<RobotDashboardIntegration>() != null) return;
            nav.gameObject.AddComponent<RobotDashboardIntegration>();
        }

        private void Awake()
        {
            navigation = GetComponent<NavigationCoordinator>();
            if (navigation == null || navigation.IsTrainingMission) { enabled = false; return; }
            navigation.UseDashboardStart();
            a = CreateSource("A", "L-DSF-01", "축정렬불량", false);
            b = CreateSource("B", "L-SF-04", "베어링불량", true);
            bridge = gameObject.AddComponent<EquipmentNetworkBridge>();
            bridge.Configure(8765, a, b);
            bridge.MissionSnapshot = () => new
            {
                sessionId, state = navigation.State.ToString(), detail = navigation.StatusDetail,
                canStart = !started && navigation.State == NavigationCoordinator.MissionState.Idle,
                inspections
            };
            bridge.MissionCommand = Execute;
            navigation.InspectionCompleted += OnInspection;
        }

        private CsvReplayDataSource CreateSource(string id, string sourceId, string fault, bool faulted)
        {
            var child = new GameObject("Dashboard Equipment " + id);
            child.transform.SetParent(transform, false);
            var source = child.AddComponent<CsvReplayDataSource>();
            source.Configure(id, "data", "2.2kW", sourceId, fault, faulted);
            return source;
        }

        private string Execute(string action)
        {
            if (!isActiveAndEnabled || navigation.IsTrainingMission) return "Dashboard control is disabled";
            if (action == "mission_stop")
            {
                navigation.StopFromDashboard();
                // ResetMission does not teleport the robot. Starting from an arbitrary
                // position would corrupt route assumptions; require a fresh Play session.
                started = true;
                return null;
            }
            if (action != "mission_start") return "Unsupported robot action";
            if (started || navigation.State != NavigationCoordinator.MissionState.Idle)
                return "Mission already started. Restart Unity Play for a new run.";
            started = true;
            navigation.StartEquipmentAAndBMission();
            return navigation.State == NavigationCoordinator.MissionState.Fault ? navigation.StatusDetail : null;
        }

        private void OnInspection(string point)
        {
            var source = point.StartsWith("inspect_point_A", StringComparison.Ordinal) ? a :
                point.StartsWith("inspect_point_B", StringComparison.Ordinal) ? b : null;
            var snapshot = source != null ? source.Latest : null;
            inspections.Add(new
            {
                id = sessionId + "-" + (inspections.Count + 1), point,
                equipmentId = snapshot?.EquipmentId ?? "", completedAtUtc = DateTime.UtcNow,
                sourceEquipmentId = snapshot?.SourceEquipmentId ?? "",
                filePath = snapshot?.Vibration?.SourcePath ?? "",
                error = snapshot?.Vibration == null ? "점검 시 진동 CSV가 없습니다." : ""
            });
        }

        private void OnDestroy()
        {
            if (navigation != null) navigation.InspectionCompleted -= OnInspection;
        }
    }
}
