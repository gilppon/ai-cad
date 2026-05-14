import React, { useState } from 'react';
import LossSimulator from '../components/LossSimulator';
import CtaButton from '../components/CtaButton';

// Mock Data & Logic for A/B Testing Tracking (Business KPI)
const trackEvent = async (eventName: string, eventId: string) => {
  console.log(`[Tracking]: Event Name: ${eventName}, Event ID: ${eventId}`);
  // 실제 구현에서는 여기에 Supabase API 호출 로직이 들어감 (e.g., await supabase.from('user_events').insert(...))
};

const LandingPageTest = () => {
  const [testVariant, setTestVariant] = useState<'loss' | 'gain'>('loss');
  const [simulationResult, setSimulationResult] = useState<number>(0);

  const handleSimulateLoss = (lossValue: number) => {
    setSimulationResult(lossValue);
  };

  const handleCtaClick = async (variant: 'loss' | 'gain') => {
    const eventId = `CTA_Test_${variant.toUpperCase()}_${Date.now()}`; // A/B 테스트 이벤트 ID 생성
    console.log(`[A/B Test Triggered]: ${eventId}`);
    await trackEvent('cta_click_attempt', eventId);
  };

  return (
    <div className="min-h-screen bg-gray-900 p-12 font-sans">
      <header className="text-center mb-16">
        <h1 className="text-5xl font-extrabold text-white mb-4">Loss Avoidance Experience</h1>
        <p className="text-xl text-gray-300">손실 회피를 통해 진정한 가치를 발견하세요.</p>
      </header>

      {/* 1. Loss Simulator Section */}
      <section className="max-w-4xl mx-auto mb-20 bg-gray-800 p-8 rounded-xl shadow-2xl border border-red-500/30">
        <LossSimulator onSimulateLoss={handleSimulateLoss} />
      </section>

      {/* 2. CTA Section */}
      <section className="max-w-4xl mx-auto bg-gray-800 p-10 rounded-xl shadow-2xl border border-blue-500/30">
        <h2 className="text-3xl font-bold text-white mb-6 text-center">다음 단계로 나아가기</h2>
        <div className="flex justify-center space-x-8">
          {/* Loss CTA */}
          <CtaButton
            label="손실 경험하기 (Loss)"
            variant="loss"
            onClick={() => handleCtaClick('loss')}
            eventId={`CTA_Test_LOSS_${Date.now()}`}
          />
          {/* Gain CTA */}
          <CtaButton
            label="가치 획득하기 (Gain)"
            variant="gain"
            onClick={() => handleCtaClick('gain')}
            eventId={`CTA_Test_GAIN_${Date.now()}`}
          />
        </div>
      </section>

    </div>
  );
};

export default LandingPageTest;