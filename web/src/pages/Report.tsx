import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { ArrowLeft, Download, CheckCircle, XCircle, FileText } from 'lucide-react';

interface RoomReport {
  room_id: int;
  room_kind: string;
  violations: any[];
}

interface ComplianceReport {
  page_index: number;
  metrics: any;
  overall_status: 'PASS' | 'FAIL';
  room_reports: RoomReport[];
  slm_prompt_context: string;
  slm_assessment?: {
    summary: string;
    action_items: string[];
  };
}

export default function Report() {
  const { projectId } = useParams();
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) throw new Error("No active session");

        const res = await fetch(`http://localhost:8000/api/v1/projects/${projectId}/compliance-report`, {
          headers: {
            'Authorization': `Bearer ${session.access_token}`
          }
        });

        if (!res.ok) throw new Error("Failed to fetch compliance report");
        const data = await res.json();
        setReport(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [projectId]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen bg-gray-50">
        <p className="text-gray-500 font-medium">Loading Compliance Report...</p>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="flex justify-center items-center h-screen bg-gray-50 flex-col gap-4">
        <p className="text-red-500 font-medium">Error: {error}</p>
        <Link to="/dashboard" className="text-blue-600 hover:underline">Back to Dashboard</Link>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-6 bg-gray-50 min-h-screen">
      <div className="flex justify-between items-center mb-8">
        <div className="flex items-center gap-4">
          <Link to="/dashboard" className="p-2 text-gray-500 hover:text-gray-900 bg-white rounded-full shadow-sm">
            <ArrowLeft size={20} />
          </Link>
          <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-2">
            <FileText className="text-blue-600" />
            Compliance Report
          </h1>
        </div>
        <a
          href={`http://localhost:8000/api/v1/projects/${projectId}/download-ifc`}
          className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition shadow-sm font-medium"
        >
          <Download size={18} />
          Download 3D Model (IFC)
        </a>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="col-span-1 md:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
            SLM Assessment
            {report.overall_status === 'PASS' ? (
              <span className="px-2 py-1 bg-green-100 text-green-700 text-sm rounded-md font-semibold ml-auto">PASS</span>
            ) : (
              <span className="px-2 py-1 bg-red-100 text-red-700 text-sm rounded-md font-semibold ml-auto">FAIL</span>
            )}
          </h2>
          <div className="text-gray-700 mb-4 bg-gray-50 p-4 rounded-lg leading-relaxed">
            {report.slm_assessment?.summary || "No assessment available."}
          </div>
          {report.slm_assessment?.action_items && report.slm_assessment.action_items.length > 0 && (
            <div>
              <h3 className="text-sm font-bold text-gray-900 mb-2 uppercase tracking-wide">Action Items</h3>
              <ul className="list-disc list-inside text-red-600 space-y-1">
                {report.slm_assessment.action_items.map((item, idx) => (
                  <li key={idx} className="text-sm">{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="col-span-1 bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex flex-col justify-center items-center text-center">
          <div className="w-24 h-24 rounded-full flex items-center justify-center mb-4 bg-blue-50">
             {report.overall_status === 'PASS' ? (
               <CheckCircle size={48} className="text-green-500" />
             ) : (
               <XCircle size={48} className="text-red-500" />
             )}
          </div>
          <h3 className="text-lg font-semibold text-gray-800">Overall Status</h3>
          <p className="text-sm text-gray-500 mt-1">Based on Deterministic Rules</p>
        </div>
      </div>

      <h2 className="text-2xl font-bold text-gray-800 mb-6">Room Details</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {report.room_reports.map((room) => {
          const isPass = room.violations.length === 0;
          return (
            <div key={room.room_id} className={`p-5 rounded-lg border shadow-sm ${isPass ? 'bg-white border-gray-200' : 'bg-red-50 border-red-200'}`}>
              <div className="flex justify-between items-center mb-3">
                <span className="font-bold text-lg text-gray-900">Room {room.room_id} ({room.room_kind})</span>
                {isPass ? (
                  <span className="text-green-600 flex items-center gap-1 font-medium text-sm"><CheckCircle size={16}/> Passed</span>
                ) : (
                  <span className="text-red-600 flex items-center gap-1 font-medium text-sm"><XCircle size={16}/> Failed</span>
                )}
              </div>
              
              {!isPass && (
                <div className="mt-3 space-y-2">
                  {room.violations.map((v, idx) => (
                    <div key={idx} className="text-sm text-red-700 bg-white p-2 rounded border border-red-100">
                      <strong>{v.rule_name}</strong>: {v.message}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
