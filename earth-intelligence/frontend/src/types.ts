export interface ClassStat {
  class_id: number;
  name: string;
  color: string;
  area_km2: number;
  percent: number;
}

export interface YearResult {
  year: number;
  scenes: number;
  satellite_url: string;
  landcover_url: string;
  total_km2: number;
  stats: ClassStat[];
}

export interface ImageryResult {
  place: string;
  query: string;
  lat: number;
  lon: number;
  radius_km: number;
  years: YearResult[];
  errors: Record<string, string>;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  results?: ImageryResult[];
  isError?: boolean;
}

export interface ChatResponse {
  reply: string;
  results: ImageryResult[];
}
