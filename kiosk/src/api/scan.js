const BASE_URL = import.meta.env.VITE_API_URL || window.location.origin

export async function submitBarcode(barcode) {
  const resp = await fetch(`${BASE_URL}/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ barcode }),
  })
  if (!resp.ok) throw new Error("扫描请求失败")
  return resp.json()
}
