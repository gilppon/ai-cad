import { createClient } from "@/utils/supabase/client";

/**
 * FastAPI 백엔드 호출용 인증 헤더를 Supabase 세션에서 조립한다. (SP1/S-2)
 * 소스 코드에 JWT를 하드코딩하는 것은 금지되며, 항상 실제 로그인 세션 토큰을 사용한다.
 */
export async function getAuthHeaders(): Promise<Record<string, string>> {
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  const accessToken = data.session?.access_token;
  if (!accessToken) {
    throw new Error("NOT_AUTHENTICATED");
  }
  return { Authorization: `Bearer ${accessToken}` };
}
