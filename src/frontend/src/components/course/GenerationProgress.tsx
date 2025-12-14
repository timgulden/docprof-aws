interface GenerationProgressProps {
  progressPercent: number;
  currentStep?: string;
  generationProgress?: string;
  elapsedSeconds: number;
  generationStartTime?: number | null;
}

export const GenerationProgress = ({
  progressPercent,
  currentStep,
  generationProgress,
  elapsedSeconds,
  generationStartTime,
}: GenerationProgressProps) => {
  const displayPercent = progressPercent > 0 ? progressPercent : 5; // Show at least 5% for visual feedback
  const displayStep = currentStep || generationProgress || "Initializing...";
  
  return (
    <div className="flex flex-col items-center justify-center h-full p-6">
      <div className="relative w-80 mb-6">
        {/* Progress bar background */}
        <div className="w-full h-4 bg-gray-200 rounded-full overflow-hidden">
          {/* Real progress bar */}
          <div 
            className="h-full bg-blue-600 rounded-full transition-all duration-500 ease-out" 
            style={{ width: `${displayPercent}%` }}
          ></div>
        </div>
        <div className="mt-2 text-center">
          <span className="text-sm font-medium text-gray-700">{displayPercent}%</span>
        </div>
      </div>
      <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-4"></div>
      <p className="text-lg font-medium text-gray-700 mb-2">Generating Lecture</p>
      <p className="text-sm text-gray-600 mb-1">{displayStep}</p>
      {generationStartTime && (
        <p className="text-xs text-gray-500 mt-2">
          {(() => {
            const minutes = Math.floor(elapsedSeconds / 60);
            const seconds = elapsedSeconds % 60;
            return `Elapsed: ${minutes}:${seconds.toString().padStart(2, '0')}`;
          })()}
        </p>
      )}
    </div>
  );
};

