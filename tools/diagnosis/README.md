# WPF + robot mission + vibration diagnosis

## Run on this PC

1. Open the existing `Assets/jetbot_env.unity`. Stop Play if already running,
   wait for script compilation, then enter Play again.
2. The robot now waits for WPF instead of automatically starting. The runtime
   integration attaches only to `jetbot_env` / `EquipmentInspectionDemo`, and
   skips training mode. No new scene, camera, or robot is created.
3. From the project root run:

   ```powershell
   dotnet run --project gui/MarineMonitor/MarineMonitor.csproj
   ```

4. Click **Unity 연결**, then **A+B 점검 임무 시작**. Existing route, PPO,
   ADAS and cornering controls remain in charge of driving.
5. At A1, A2, B2, B1 inspection completion, WPF analyzes that equipment's
   current original vibration CSV. Each result identifies the point, equipment,
   file, sample count, four independent probabilities and 0.5 threshold.
6. **임무 중단 / 정지** cancels avoidance and stops the mission. Starting again
   requires a new Play session: resetting mission state does not reposition the
   robot. A closed/disconnected WPF does NOT automatically stop Unity.

Existing EXE builds must be rebuilt with these scripts. For player use, copy
the `data` directory beside the player; the WPF diagnosis process must be able
to read the same vibration files under the project `data/vibration` root.
If using a separate deployment root, set `SHIP_ROBOT_PROJECT` and place the
same `tools/diagnosis` and `data` layout there.

## Dependencies

The WPF projects target .NET 10 (installed SDK on this PC). A dedicated
`.venv-diagnosis` was created and populated; the PPO training environment was
not modified. On another PC, use Python 3.12 and:

```powershell
py -3.12 -m venv .venv-diagnosis
.venv-diagnosis/Scripts/python.exe -m pip install -r tools/diagnosis/requirements.txt
```

An explicit `SHIP_DIAGNOSIS_PYTHON` absolute executable path can override the
default virtual environment. Inference is a hidden, asynchronous subprocess,
one job at a time, with a 45-second timeout. Failures are displayed as
**미판정**, never normal. New Unity sessions clear old inspection rows and
cancel obsolete inference. Within a session, reconnecting does not duplicate
already received inspections. Results are session-local, not an audit archive.

## Model and preprocessing contract

- Four uploaded JSONs are copied unchanged under `models`; `manifest.json`
  records uploaded filenames and SHA-256. All four uploaded copies are
  byte-identical to their earlier same-category local files. They are still
  sourced from the newly attached files, including `Rotating body_model (1)`.
- `XGBoost.py` trains with normal=0 and abnormal=1, saves the model, THEN flips
  evaluation labels. Inference therefore uses `predict_proba(...)[0,1] >= 0.5`
  for abnormal. PDF's normal=1 convention is evaluation display only.
- Input is **vibration**, not current, using the entire CSV (skip 9 metadata
  rows; numeric columns 0/1; remove missing/nonfinite entries; linear detrend).
- No separate scaler. Same 26 ordered features as model.feature_names:
  population STD, Fisher kurtosis, symmetric Hann FFT window, `2/N` amplitude,
  zero DC, bands [0,100), [100,500), [500,min(2000,Nyquist)).
- Display telemetry at ~10 Hz is NOT the original waveform and is never used
  for these features. Analysis uses a complete prerecorded CSV even if its
  replay cursor has not reached the end: **offline replay demonstration, not
  causal real-time fault detection or actual robot measurement**.
- Simulation labels are not prediction inputs. The four binary classifiers
  are shown independently; their agreement is not a validated multiclass
  diagnosis or calibrated combined confidence. Current signals remain charts.
- Degenerate/nonfinite features, missing files, bad hashes and invalid model
  outputs fail closed as unassessed. Only CSV paths resolving under the local
  data/vibration folder are allowed.

## Verification

```powershell
.venv-diagnosis/Scripts/python.exe tools/diagnosis/test_diagnosis.py --reference-zip "C:/Users/kimsumi/Downloads/XGBoost.zip" -v
dotnet build gui/MarineMonitor/MarineMonitor.csproj
dotnet build gui/UnityIntegration.Check/UnityIntegration.Check.csproj
dotnet build gui/MarineMonitor.Tests/MarineMonitor.Tests.csproj
dotnet gui/MarineMonitor.Tests/bin/Debug/net10.0/MarineMonitor.Tests.dll gui/MarineMonitor/bin/Debug/net10.0-windows/MarineMonitor.exe
```

The parity test executes only the four named feature functions from the supplied
reference AST, not its training/notebook top-level code. Three CSV fixtures
(normal, axis fault, bearing fault) agree with all four original extractors at
1e-12 tolerance. Tests load all real models. The WPF smoke uses a **test server**
to exercise command ACK, completion, single-result deduplication, real inference,
and disconnect behavior; it does not exercise real Unity driving. The Unity
reference-assembly compile is also not a substitute for a full Play rehearsal.

## Protocol extension (v1-compatible optional fields)

Telemetry now includes optional `mission` with `sessionId`, `state`, `detail`,
`canStart`, `inspections`. Inspection records are retained for the Play session
so reconnect can recover missed completions. `vibration.sourcePath` identifies
the local replay file. Legacy telemetry without a mission still works.

Commands use existing request/ACK/deduplication handling with `equipmentId`
`robot` and action `mission_start` or `mission_stop`. Navigation runs on the
Unity main thread. Replay commands for A/B are unchanged. No inference is
performed on the Unity frame loop. Network remains loopback-only.
