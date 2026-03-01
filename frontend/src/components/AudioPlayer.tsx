/**
 * Audio player component for playing generated speech.
 * Wraps the HTML5 audio element with custom styling.
 * Used to play TTS-generated audio files directly in the browser.
 */

interface AudioPlayerProps {
  audioUrl: string;
}

export default function AudioPlayer({ audioUrl }: AudioPlayerProps) {
  return (
    <div className="mt-4">
      <audio 
        controls 
        className="w-full"
        src={audioUrl}
      >
        Your browser does not support the audio element.
      </audio>
    </div>
  );
}
