import { createClient } from "@supabase/supabase-js";

// 환경변수 추출 (부재 시 개발용 Mock 샌드박스 URL 제공으로 서킷 브레이커 작동)
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://mock-supabase.japanbuild.jp";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock-key";

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// B2B 세션 관리 헬퍼 (로컬스토리지 백업 체계를 갖추어 Supabase 오프라인 상황 대응)
export interface UserSession {
  email: string;
  tenant_id: string;
  company_name: string;
  subscription_tier: "LIGHT" | "BUSINESS" | "ENTERPRISE";
  credits: number;
}

const STORAGE_KEY = "japanbuild_b2b_session";

// 디폴트 Mock 세션 (Supabase 미연동 로컬 개발용 시각적 완성도 보증)
const DEFAULT_MOCK_SESSION: UserSession = {
  email: "representative@gilppon-const.co.jp",
  tenant_id: "tenant_gilppon_9982",
  company_name: "ギルポン建設株式会社 (길폰 건설 주식회사)",
  subscription_tier: "ENTERPRISE",
  credits: 400
};

export const getLocalSession = (): UserSession => {
  if (typeof window === "undefined") return DEFAULT_MOCK_SESSION;
  const stored = localStorage.getItem(STORAGE_KEY);
  if (!stored) {
    // 처음 진입 시 Mock 세션을 기본값으로 이식하여 끊김없는 UX 제공
    localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_MOCK_SESSION));
    return DEFAULT_MOCK_SESSION;
  }
  try {
    return JSON.parse(stored);
  } catch {
    return DEFAULT_MOCK_SESSION;
  }
};

export const saveLocalSession = (session: UserSession): void => {
  if (typeof window !== "undefined") {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  }
};

export const clearLocalSession = (): void => {
  if (typeof window !== "undefined") {
    localStorage.removeItem(STORAGE_KEY);
  }
};
