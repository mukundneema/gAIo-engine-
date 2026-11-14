import type { ImageryResult, YearResult } from "./types";

function YearColumn({ y }: { y: YearResult }) {
  const shown = y.stats.filter((s) => s.percent > 0).sort((a, b) => b.percent - a.percent);
  return (
    <div className="year-col">
      <h4>{y.year}</h4>
      <figure>
        <img src={y.satellite_url} alt={`Satellite composite ${y.year}`} loading="lazy" />
        <figcaption>Sentinel-2 composite · {y.scenes} scenes</figcaption>
      </figure>
      <figure>
        <img src={y.landcover_url} alt={`Land-cover map ${y.year}`} loading="lazy" />
        <figcaption>Dynamic World land cover</figcaption>
      </figure>
      <div className="stackbar" role="img" aria-label={`Land-cover mix ${y.year}`}>
        {shown.map((s) => (
          <span
            key={s.class_id}
            style={{ width: `${s.percent}%`, background: s.color }}
            title={`${s.name}: ${s.percent}%`}
          />
        ))}
      </div>
      <table>
        <tbody>
          {shown.map((s) => (
            <tr key={s.class_id}>
              <td>
                <i style={{ background: s.color }} />
                {s.name}
              </td>
              <td className="num">{s.area_km2.toFixed(1)} km²</td>
              <td className="num">{s.percent.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Results({ data }: { data: ImageryResult }) {
  const failed = Object.entries(data.errors);
  return (
    <section className="results">
      <header>
        <strong>{data.place}</strong>
        <span>
          {data.lat.toFixed(3)}, {data.lon.toFixed(3)} · {data.radius_km} km radius
        </span>
      </header>
      <div className="year-grid">
        {data.years.map((y) => (
          <YearColumn key={y.year} y={y} />
        ))}
      </div>
      {failed.length > 0 && (
        <p className="warn">
          Not retrieved: {failed.map(([yr, msg]) => `${yr} (${msg})`).join("; ")}
        </p>
      )}
    </section>
  );
}
