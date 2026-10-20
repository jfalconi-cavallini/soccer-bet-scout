export function ProbBars({
  home,
  draw,
  away,
}: {
  home: number;
  draw: number;
  away: number;
}) {
  return (
    <div className="probs" aria-label="Win, draw, and away probabilities">
      <div className="prob-line">
        <span>Home</span>
        <div className="track"><span className="home-bar" style={{ width: `${home}%` }} /></div>
        <b>{home.toFixed(0)}%</b>
      </div>
      <div className="prob-line">
        <span>Draw</span>
        <div className="track"><span className="draw-bar" style={{ width: `${draw}%` }} /></div>
        <b>{draw.toFixed(0)}%</b>
      </div>
      <div className="prob-line">
        <span>Away</span>
        <div className="track"><span className="away-bar" style={{ width: `${away}%` }} /></div>
        <b>{away.toFixed(0)}%</b>
      </div>
    </div>
  );
}
