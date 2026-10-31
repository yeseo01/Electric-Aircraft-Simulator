// Keep the larger WebGL bundle out of the initial dashboard download.
export async function loadPlotly3d() {
  const { default: plotly } = await import('plotly.js-gl3d-dist-min')
  return plotly
}
