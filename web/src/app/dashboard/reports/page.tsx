"use client";

import { useState, useEffect, useCallback } from "react";
import { FileText, Download, Calendar, RefreshCw, AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";
import { API_BASE_URL } from "@/utils/api";
import { getAuthHeaders } from "@/utils/apiAuth";

/**
 * SP6/P0-4: 과거 이 페이지는 하드코딩된 가짜 프로젝트 2건
 * 하드코딩된 가짜 프로젝트 2건(도쿄 아오야마, 오사카 우메다)을 표시했고,
 * 각 항목에 조작된 적합 판정(適合 / 一部不適合)과 법적 소견을 붙여 두었다.
 * 헤더 문구는 "보험사 청구 및 인허가 신청 첨부 서류로 즉시 활용 가능"이라고
 * 단정하고 있었다 — 근거 없는 표시이며 고객 오판을 유발한다.
 *
 * 현재: 실제 백엔드 `GET /api/v1/projects` 목록만 표시한다.
 *       판정은 백엔드 컴플라이언스 엔진 응답으로만 렌더링한다.
 */

interface Project {
  id: string;
  original_filename: string;
  status: string;
  created_at?: string;
  updated_at?: string;
  error_message?: string | null;
}

interface RuleEvaluation {
  rule_id: string;
  rule_name: string;
  status: string;
  reason?: string;
}

interface ComplianceReport {
  status: string;
  total_violations: number;
  room_results: { room_id: string; room_kind: string; evaluations: RuleEvaluation[] }[];
  slm_assessment?: { opinion_ja?: string } | string | null;
}

const STATUS_LABEL: Record<string, { text: string; className: string }> = {
  pending: { text: "대기", className: "bg-neutral-700/20 text-neutral-300 border-neutral-600" },
  processing: { text: "분석 중", className: "bg-blue-500/10 text-blue-400 border-blue-500/25" },
  completed: { text: "완료", className: "bg-emerald-500/10 text-emerald-400 border-emerald-500/25" },
  error: { text: "실패", className: "bg-red-500/10 text-red-400 border-red-500/25" },
};

export default function ReportsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [reports, setReports] = useState<Record<string, ComplianceReport>>({});
  const [reportErrors, setReportErrors] = useState<Record<string, string>>({});

  const loadProjects = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/projects`, {
        headers: await getAuthHeaders(),
      });

      if (!res.ok) {
        throw new Error(
          res.status === 401
            ? "로그인이 만료되었습니다. 다시 로그인해 주십시오."
            : `프로젝트 목록을 불러오지 못했습니다 (HTTP ${res.status}).`
        );
      }

      const data = await res.json();
      setProjects(data.projects || []);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "알 수 없는 오류가 발생했습니다.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  /** 적합 판정 조회 — 백엔드 응답으로만 렌더링한다. 프론트에서 판정을 만들지 않는다. */
  const loadCompliance = async (projectId: string) => {
    if (reports[projectId]) {
      setExpandedId(expandedId === projectId ? null : projectId);
      return;
    }

    setReportErrors((prev) => ({ ...prev, [projectId]: "" }));
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/v1/projects/${projectId}/compliance-report`,
        { headers: await getAuthHeaders() }
      );

      if (!res.ok) {
        throw new Error(
          res.status === 404
            ? "아직 컴플라이언스 데이터가 생성되지 않았습니다."
            : `판정을 불러오지 못했습니다 (HTTP ${res.status}).`
        );
      }

      const data = await res.json();
      setReports((prev) => ({ ...prev, [projectId]: data }));
      setExpandedId(projectId);
    } catch (err) {
      setReportErrors((prev) => ({
        ...prev,
        [projectId]: err instanceof Error ? err.message : "판정을 불러오지 못했습니다.",
      }));
      setExpandedId(projectId);
    }
  };

  /** PDF 다운로드 — 인증 헤더가 필요하므로 window.open() 이 아닌 blob fetch 를 사용한다. */
  const handleDownloadPDF = async (projectId: string) => {
    setDownloadingId(projectId);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/v1/projects/${projectId}/pdf-report`,
        { headers: await getAuthHeaders() }
      );

      if (!res.ok) {
        throw new Error(
          res.status === 404
            ? "아직 리포트가 생성되지 않았습니다."
            : `리포트 생성에 실패했습니다 (HTTP ${res.status}).`
        );
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Japanbuild_BIM3D_Compliance_${projectId}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setReportErrors((prev) => ({
        ...prev,
        [projectId]: err instanceof Error ? err.message : "리포트를 내려받지 못했습니다.",
      }));
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-500">
      <div>
        <h3 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
          <FileText className="w-5 h-5 text-blue-500" />
          <span>컴플라이언스 리포트</span>
        </h3>
        <p className="text-xs text-neutral-400 max-w-xl leading-normal">
          업로드한 도면의 법규 판정 결과입니다. 판정은 서버의 컴플라이언스 엔진이
          산출하며, 데이터가 부족한 항목은 <strong className="text-neutral-300">판정 불가</strong>로
          표시됩니다. 제출용 문서로 사용하기 전에 판정 근거를 반드시 확인하십시오.
        </p>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-3 text-neutral-500 text-sm py-12 justify-center">
          <RefreshCw className="w-4 h-4 animate-spin" />
          <span>프로젝트 목록을 불러오는 중...</span>
        </div>
      ) : loadError ? (
        <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-6 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
          <div className="flex-1">
            <p className="text-red-300 text-sm font-semibold">목록을 불러올 수 없습니다</p>
            <p className="text-red-400/80 text-xs mt-1">{loadError}</p>
          </div>
          <button
            onClick={loadProjects}
            className="px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-white text-xs rounded-lg cursor-pointer"
          >
            다시 시도
          </button>
        </div>
      ) : projects.length === 0 ? (
        <div className="bg-neutral-900 border border-neutral-800 rounded-3xl p-10 text-center">
          <p className="text-neutral-300 text-sm font-semibold mb-1">아직 업로드된 도면이 없습니다</p>
          <p className="text-neutral-500 text-xs">
            대시보드에서 도면 PDF를 업로드하면 이곳에 판정 리포트가 생성됩니다.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {projects.map((project) => {
            const status = STATUS_LABEL[project.status] ?? {
              text: project.status,
              className: "bg-neutral-700/20 text-neutral-300 border-neutral-600",
            };
            const report = reports[project.id];
            const isExpanded = expandedId === project.id;
            const error = reportErrors[project.id];

            return (
              <div
                key={project.id}
                className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5"
              >
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                  <div className="space-y-1.5 min-w-0">
                    <h4 className="text-sm font-bold text-white truncate">
                      {project.original_filename}
                    </h4>
                    <div className="flex items-center gap-3 text-xs text-neutral-500">
                      {project.created_at && (
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5" />
                          {new Date(project.created_at).toLocaleDateString("ja-JP")}
                        </span>
                      )}
                      <span className="font-mono">{project.id.slice(0, 8)}</span>
                    </div>
                  </div>

                  <span className={`px-3 py-1 rounded-full text-xs font-bold border ${status.className}`}>
                    {status.text}
                  </span>
                </div>

                {project.status === "error" && project.error_message && (
                  <p className="mt-3 text-xs text-red-400/90 bg-red-500/5 border border-red-500/20 rounded-lg px-3 py-2">
                    처리 실패: {project.error_message}
                  </p>
                )}

                {error && (
                  <p className="mt-3 text-xs text-amber-400/90 bg-amber-500/5 border border-amber-500/20 rounded-lg px-3 py-2">
                    {error}
                  </p>
                )}

                <div className="flex flex-wrap gap-2 mt-4">
                  <button
                    onClick={() => loadCompliance(project.id)}
                    className="px-4 py-2 bg-neutral-800 hover:bg-neutral-700 text-white text-xs font-semibold rounded-lg flex items-center gap-2 cursor-pointer transition-colors"
                  >
                    {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                    <span>판정 조회</span>
                  </button>

                  <button
                    onClick={() => handleDownloadPDF(project.id)}
                    disabled={downloadingId === project.id}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-neutral-800 disabled:text-neutral-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 cursor-pointer transition-colors"
                  >
                    {downloadingId === project.id ? (
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Download className="w-3.5 h-3.5" />
                    )}
                    <span>PDF 내려받기</span>
                  </button>
                </div>

                {isExpanded && report && (
                  <div className="mt-4 p-4 bg-neutral-950 rounded-xl border border-neutral-800">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-[10px] font-bold text-neutral-500 uppercase tracking-widest">
                        서버 판정 결과
                      </span>
                      <span
                        className={`text-xs font-bold px-2.5 py-1 rounded-md border ${
                          report.total_violations === 0
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                            : "bg-orange-500/10 text-orange-400 border-orange-500/20"
                        }`}
                      >
                        위반 {report.total_violations}건
                      </span>
                    </div>

                    <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
                      {report.room_results.map((room) => {
                        const fails = room.evaluations.filter((e) => e.status === "FAIL");
                        return (
                          <div key={room.room_id} className="text-xs">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-semibold text-neutral-200">
                                Room {room.room_id}
                              </span>
                              <span className="text-neutral-500">({room.room_kind})</span>
                              {fails.length === 0 && (
                                <span className="text-emerald-400">위반 없음</span>
                              )}
                            </div>
                            {fails.map((f) => (
                              <div key={f.rule_id} className="pl-3 text-orange-400/90">
                                · [{f.rule_id}] {f.reason ?? f.rule_name}
                              </div>
                            ))}
                          </div>
                        );
                      })}
                      {report.room_results.length === 0 && (
                        <p className="text-xs text-neutral-500">
                          판정 대상 공간이 없습니다.
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
