import React, { useState } from 'react';

// Designer가 정의한 HSL 및 Z-Axis 기반 스타일 변수 (예시)
const styleConfig = {
  pain: { hue: 210, saturation: 70, lightness: 40 }, // Pain (Reddish/Darker)
  gain: { hue: 120, saturation: 85, lightness: 60 }, // Gain (Bluish/Brighter)
};

interface LossSimulatorProps {
  onSimulateLoss: (lossValue: number) => void;
}

const LossSimulator: React.FC<LossSimulatorProps> = ({ onSimulateLoss }) => {
  const [loss, setLoss] = useState(0);

  const handleSimulate = () => {
    // 실제 로직에서는 API 호출을 통해 손실 값을 받아와야 하지만, 여기서는 시뮬레이션 값 사용
    onSimulateLoss(Math.floor(Math.random() * 100));
  };

  return (
    <div className="p-6 border-2 border-red-500 rounded-lg shadow-xl bg-gray-900 transition-all duration-500">
      <h3 className="text-xl font-bold text-white mb-4">손실 시뮬레이터 (Loss Simulator)</h3>
      <p className="text-sm text-gray-400 mb-6">현재 감정 상태를 시뮬레이션합니다. (Pain $\rightarrow$ Gain 흐름)</p>

      {/* Z-Axis/HSL 기반 시각화 영역 */}
      <div style={{ background: `hsl(${styleConfig.pain.hue}, ${styleConfig.pain.saturation}%, ${styleConfig.pain.lightness}%)` }} className="h-40 rounded-md mb-6 transition-colors duration-500">
        <p className="text-white text-center pt-10 font-semibold">Pain State</p>
      </div>

      <div style={{ background: `hsl(${styleConfig.gain.hue}, ${styleConfig.gain.saturation}%, ${styleConfig.gain.lightness}%)` }} className="h-40 rounded-md transition-colors duration-500">
        <p className="text-white text-center pt-10 font-semibold">Gain State</p>
      </div>

      <div className="mt-6 flex justify-between items-center">
        <p className="text-lg font-medium text-white">시뮬레이션된 손실: <span className="text-red-400 font-bold">{loss}%</span></p>
        <button
          onClick={handleSimulate}
          className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded transition duration-200 shadow-lg"
        >
          손실 시뮬레이션 실행
        </button>
      </div>
    </div>
  );
};

export default LossSimulator;