"use client";

import { useState, useEffect } from "react";
import { FileText, Download, Building, ShieldCheck, Calendar, RefreshCw } from "lucide-react";
import { getLocalSession, UserSession } from "@/utils/supabase";

interface ReportItem {
  id: string;
  projectName: string;
  inspectDate: string;
  complianceStatus: "PASS" | "WARNING" | "FAIL";
  lightVerdict: string;
  heightVerdict: string;
  leakOpinion: string;
}

export default function ReportsPage() {
  const [session, setSession] = useState<UserSession | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  
  const [reports, setReports] = useState<ReportItem[]>([
    {
      id: "mock_project_123",
      projectName: "도쿄 아오야마 맨션 201호 준공 도면 (Tokyo Aoyama Mansions)",
      inspectDate: "2026-05-20",
      complianceStatus: "PASS",
      lightVerdict: "適合 (PASS)",
      heightVerdict: "適合 (PASS)",
      leakOpinion: "専有部分 (욕실/ toilet 배수 지관 하자 책임 유력)"
    },
    {
      id: "mock_project_456",
      projectName: "오사카 우메다 B블럭 상업시설 층고 보정 도면 (Osaka Umeda Commercial)",
      inspectDate: "2026-05-18",
      complianceStatus: "WARNING",
      lightVerdict: "適合 (PASS)",
      heightVerdict: "一部不適合 (WARNING - 국부 층고 부족)",
      leakOpinion: "공용부분 (SHAFT 파이프 샤프트 내 누수)"
    }
  ]);

  useEffect(() => {
    setSession(getLocalSession());
  }, []);

  const handleDownloadPDF = async (reportId: string) => {
    setDownloadingId(reportId);
    try {
      // 1. 실제 백엔드의 ReportLab PDF 발행 엔드포인트 연동 시도 (/pdf-report GET 라우트 호출)
      // (만약 백엔드가 비활성 상태이면 로컬 헬퍼 다운로드 링크로 대체하는 서킷 브레이커)
      const res = await fetch(`/api/v1/projects/${reportId}/pdf-report`, {
        method: "GET"
      });

      if (res.ok) {
        // 백엔드에서 반환된 PDF 바이너리 수령
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `Japanbuild_BIM3D_Compliance_${reportId}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      } else {
        // Fallback: 8000포트 백엔드로의 브라우저 다이렉트 트리거 제공
        alert("🌐 [백엔드 다이렉트 브로커 가동]\n백엔드 API 서버를 통해 직접 법령 합격 증명서 PDF를 생성 및 출력합니다.");
        window.open(`http://127.0.0.1:8000/api/v1/projects/${reportId}/pdf-report`, "_blank");
      }
    } catch (err) {
      console.error(err);
      // 최종 Fallback: 백엔드 URL로 직접 강제 오픈
      window.open(`http://127.0.0.1:8000/api/v1/projects/${reportId}/pdf-report`, "_blank");
    } finally {
      setDownloadingId(null);
    }
  };

  if (!session) return <div className="text-neutral-400 text-sm">로딩 중...</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-500">
      
      {/* 아카이브 헤더 설명 */}
      <div>
        <h3 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
          <FileText className="w-5 h-5 text-blue-500" />
          <span>일본 MLIT 자가 적합성 검격 PDF 아카이브</span>
        </h3>
        <p className="text-xs text-neutral-400 max-w-xl leading-normal">
          본 문서고에 보관된 리포트는 일본 건축기준법 제28조(채광률) 및 시행령 제21조(반자높이) 판정 공식 날인이 완료되어, 
          손해보험사 청구 및 확인인허가 신청 첨부 서류로 즉시 활용 가능합니다.
        </p>
      </div>

      {/* 리포트 카드 그리드 리스트 */}
      <div className="space-y-6">
        {reports.map((report) => (
          <div key={report.id} className="bg-neutral-900 border border-neutral-800 rounded-3xl p-6 relative overflow-hidden transition-all duration-300 hover:border-neutral-700">
            <div className="absolute inset-0 bg-gradient-to-r from-blue-500/5 to-transparent pointer-events-none"></div>
            
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6 mb-6">
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <span className="text-[10px] font-extrabold px-2 py-0.5 bg-neutral-950 rounded text-neutral-400">ID: {report.id}</span>
                  <span className="text-xs text-neutral-500 flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5" />
                    <span>진단일: {report.inspectDate}</span>
                  </span>
                </div>
                <h4 className="text-base font-bold text-white leading-normal">{report.projectName}</h4>
              </div>

              <span className={`px-3 py-1 rounded-full text-xs font-bold tracking-wider ${report.complianceStatus === "PASS" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-orange-500/10 text-orange-400 border border-orange-500/20 animate-pulse"}`}>
                {report.complianceStatus === "PASS" ? "適合 (PASS)" : "一部不適合 (WARNING)"}
              </span>
            </div>

            {/* 검격 요약표 */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 p-4 bg-neutral-950 rounded-2xl border border-neutral-800/80 mb-6 text-xs text-neutral-300">
              <div className="space-y-1">
                <span className="text-[9px] font-bold text-neutral-500 uppercase tracking-widest block">채광/환기 검격 (건축법 제28조)</span>
                <span className="font-semibold text-neutral-200">{report.lightVerdict}</span>
              </div>
              <div className="space-y-1">
                <span className="text-[9px] font-bold text-neutral-500 uppercase tracking-widest block">반자 높이 검격 (시행령 제21조)</span>
                <span className="font-semibold text-neutral-200">{report.heightVerdict}</span>
              </div>
              <div className="space-y-1">
                <span className="text-[9px] font-bold text-neutral-500 uppercase tracking-widest block">일본 구분소유법 누수 판정</span>
                <span className="font-semibold text-blue-400 flex items-center gap-1.5 mt-0.5">
                  <ShieldCheck className="w-4 h-4 text-blue-400" />
                  <span>{report.leakOpinion}</span>
                </span>
              </div>
            </div>

            {/* 다운로드 버튼 */}
            <button
              onClick={() => handleDownloadPDF(report.id)}
              disabled={downloadingId === report.id}
              className="px-5 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-neutral-800 disabled:text-neutral-500 text-white font-bold text-xs rounded-xl shadow-lg hover:shadow-blue-500/20 flex items-center gap-2 cursor-pointer transition-colors"
            >
              {downloadingId === report.id ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>합격서 생성 중...</span>
                </>
              ) : (
                <>
                  <Download className="w-3.5 h-3.5" />
                  <span>검격 합격 증명서 (PDF) 다운로드</span>
                </>
              )}
            </button>

          </div>
        ))}
      </div>

    </div>
  );
}
