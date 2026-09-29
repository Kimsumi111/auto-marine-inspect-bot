"""Offline CSV replay inference. No training, plotting, or label-based prediction.

Matches the four feature extractors supplied in XGBoost.zip. The original code
saves models BEFORE reversing evaluation labels: model class 1 is abnormal.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.fft import rfft, rfftfreq
from scipy.signal import detrend, windows
from scipy.stats import skew, kurtosis
import xgboost as xgb

FEATURES = ["Mean", "STD", "RMS", "Peak", "Max", "Min", "P2P", "Skewness",
            "Kurtosis", "CrestFactor", "ShapeFactor", "ImpulseFactor", "MarginFactor",
            "Dominant_Hz", "Dominant_Amp", "FFT_Mean", "FFT_STD", "Spectral_Centroid",
            "Spectral_Bandwidth", "Low_Band_Energy", "Mid_Band_Energy", "High_Band_Energy",
            "Low_Band_Ratio", "Mid_Band_Ratio", "High_Band_Ratio", "Sampling_Frequency"]
MODELS = {"axis": ("축 정렬", "axis.json"), "bearing": ("베어링", "bearing.json"),
          "belt": ("벨트", "belt.json"), "rotating": ("회전체", "rotating.json")}


def load_vibration_csv(path):
    df = pd.read_csv(path, skiprows=9, header=None, usecols=[0, 1])
    df = df.apply(pd.to_numeric, errors="coerce").dropna()
    if len(df) < 100:
        raise ValueError("유효한 진동 샘플이 100개 미만입니다.")
    time, acc = df.iloc[:, 0].to_numpy(float), df.iloc[:, 1].to_numpy(float)
    valid = np.isfinite(time) & np.isfinite(acc)
    time, acc = time[valid], acc[valid]
    if len(time) < 100:
        raise ValueError("유한한 진동 샘플이 100개 미만입니다.")
    return time, detrend(acc)


def extract_features_from_signal(time, acc):
    dt = np.diff(time)
    dt = dt[dt > 0]
    if not len(dt):
        raise ValueError("올바른 시간 간격이 없습니다.")
    fs = 1.0 / np.median(dt)
    n = len(acc)
    rms = np.sqrt(np.mean(acc ** 2))
    peak = np.max(np.abs(acc))
    abs_mean = np.mean(np.abs(acc)) + 1e-12
    amp = (2.0 / n) * np.abs(rfft(acc * windows.hann(n)))
    freq = rfftfreq(n, d=1.0 / fs)
    amp[0] = 0
    dominant = np.argmax(amp)
    total_amp = np.sum(amp) + 1e-12
    centroid = np.sum(freq * amp) / total_amp
    bandwidth = np.sqrt(np.sum((freq - centroid) ** 2 * amp) / total_amp)
    def energy(lo, hi):
        return np.sum(amp[(freq >= lo) & (freq < min(hi, fs / 2))] ** 2)
    low, mid, high = energy(0, 100), energy(100, 500), energy(500, 2000)
    total_energy = np.sum(amp ** 2) + 1e-12
    values = [np.mean(acc), np.std(acc), rms, peak, np.max(acc), np.min(acc),
              np.max(acc) - np.min(acc), skew(acc), kurtosis(acc, fisher=True),
              peak / (rms + 1e-12), rms / abs_mean, peak / abs_mean,
              peak / (np.mean(np.sqrt(np.abs(acc))) ** 2 + 1e-12), freq[dominant],
              amp[dominant], np.mean(amp), np.std(amp), centroid, bandwidth,
              low, mid, high, low / total_energy, mid / total_energy, high / total_energy, fs]
    if not np.all(np.isfinite(values)):
        raise ValueError("특징값에 NaN/무한대가 있습니다. 진단하지 않습니다.")
    return dict(zip(FEATURES, (float(x) for x in values)))


def diagnose(csv_path, data_root):
    path, root = Path(csv_path).resolve(strict=True), Path(data_root).resolve(strict=True)
    if not path.is_relative_to(root / "vibration") or path.suffix.lower() != ".csv":
        raise ValueError("허용된 data/vibration 내부의 CSV만 분석합니다.")
    time, acc = load_vibration_csv(path)
    features = extract_features_from_signal(time, acc)
    manifest_path = Path(__file__).parent / "models" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = []
    for key, (title, filename) in MODELS.items():
        model_path = manifest_path.parent / filename
        digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
        if digest != manifest[key]["sha256"]:
            raise ValueError(f"{title}: 모델 해시가 등록값과 다릅니다.")
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        if model.get_booster().feature_names != FEATURES:
            raise ValueError(f"{title}: 학습 특징 순서가 다릅니다.")
        frame = pd.DataFrame([features], columns=FEATURES)
        probability = float(model.predict_proba(frame)[0, 1])
        if not np.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("유효하지 않은 모델 출력")
        results.append(dict(key=key, title=title, abnormalProbability=probability,
                            threshold=0.5, abnormal=probability >= 0.5, modelSha256=digest))
    return dict(fileName=path.name, sampleCount=len(time), samplingFrequency=features["Sampling_Frequency"],
                mode="offline_csv_replay", results=results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--data-root", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(diagnose(args.csv, args.data_root), ensure_ascii=True, allow_nan=False))
    except Exception as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=True), file=sys.stderr)
        sys.exit(1)
