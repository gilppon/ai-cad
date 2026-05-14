import React from 'react';

interface CtaButtonProps {
  label: string;
  variant: 'loss' | 'gain'; // Z-Axis/HSL 기반 스타일 결정
  onClick: () => void;
  eventId?: string; // A/B 테스트 추적을 위한 이벤트 ID
}

const CtaButton: React.FC<CtaButtonProps> = ({ label, variant, onClick, eventId }) => {
  const baseStyles = "px-8 py-4 font-bold rounded-full text-lg transition duration-300 shadow-xl";
  let variantStyles = "";

  if (variant === 'loss') {
    // Pain State: Red/Darker tones based on Designer's rule
    variantStyles = "bg-red-600 hover:bg-red-700 text-white border-4 border-red-800 shadow-red-500/50";
  } else {
    // Gain State: Blue/Lighter tones based on Designer's rule
    variantStyles = "bg-blue-600 hover:bg-blue-700 text-white border-4 border-blue-800 shadow-blue-500/50";
  }

  return (
    <button
      onClick={onClick}
      className={`${baseStyles} ${variantStyles}`}
      aria-label={`Click to experience ${variant === 'loss' ? 'Loss' : 'Gain'} experience`}
    >
      {label}
      {eventId && <span className="ml-3 text-sm font-normal opacity-70">Event ID: {eventId}</span>}
    </button>
  );
};

export default CtaButton;