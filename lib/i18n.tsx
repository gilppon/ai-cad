'use client';

import React, { createContext, useContext, useState, ReactNode } from 'react';

export type Language = 'en' | 'ko' | 'ja' | 'zh' | 'fr' | 'de' | 'es';

interface Translations {
  [key: string]: {
    [lang in Language]: string;
  };
}

export const translations: Translations = {
  features: { en: 'Features', ko: '기능', ja: '機能', zh: '功能', fr: 'Fonctionnalités', de: 'Funktionen', es: 'Características' },
  methodology: { en: 'Methodology', ko: '방법론', ja: '方法論', zh: '方法论', fr: 'Méthodologie', de: 'Methodik', es: 'Metodología' },
  customers: { en: 'Customers', ko: '고객', ja: '顧客', zh: '客户', fr: 'Clients', de: 'Kunden', es: 'Clientes' },
  changelog: { en: 'Changelog', ko: '업데이트 내역', ja: '変更履歴', zh: '更新日志', fr: 'Journal des modifications', de: 'Änderungsprotokoll', es: 'Registro de cambios' },
  login: { en: 'Log in', ko: '로그인', ja: 'ログイン', zh: '登录', fr: 'Connexion', de: 'Anmelden', es: 'Iniciar sesión' },
  getStarted: { en: 'Get Started', ko: '시작하기', ja: 'はじめる', zh: '开始使用', fr: 'Commencer', de: 'Loslegen', es: 'Empezar' },
  intro: { en: 'Introducing GlowPoint AI 2.0', ko: 'GlowPoint AI 2.0 소개', ja: 'GlowPoint AI 2.0 のご紹介', zh: '隆重推出 GlowPoint AI 2.0', fr: 'Présentation de GlowPoint AI 2.0', de: 'Wir stellen vor: GlowPoint AI 2.0', es: 'Presentamos GlowPoint AI 2.0' },
  heroTitle1: { en: 'The new standard for', ko: '파라메트릭 모델링의', ja: 'パラメトリックモデリングの', zh: '参数化建模的', fr: 'La nouvelle norme pour', de: 'Der neue Standard für', es: 'El nuevo estándar para' },
  heroTitle2: { en: 'parametric modeling.', ko: '새로운 표준.', ja: '新基準。', zh: '新标准。', fr: 'la modélisation paramétrique.', de: 'parametrische Modellierung.', es: 'el modelado paramétrico.' },
  heroDesc: { en: 'Transform 2D sketches into production-ready 3D models instantly. Built for modern engineering teams who demand precision and speed.', ko: '2D 스케치를 즉시 프로덕션 수준의 3D 모델로 변환하세요. 정밀함과 속도를 요구하는 현대 엔지니어링 팀을 위해 제작되었습니다.', ja: '2Dスケッチを即座に本番環境で使える3Dモデルに変換します。精度とスピードを求める現代のエンジニアリングチームのために構築されました。', zh: '将 2D 草图瞬间转化为可用于生产的 3D 模型。专为追求精度和速度的现代工程团队打造。', fr: 'Transformez instantanément des croquis 2D en modèles 3D prêts pour la production. Conçu pour les équipes d\'ingénierie modernes qui exigent précision et rapidité.', de: 'Verwandeln Sie 2D-Skizzen sofort in produktionsreife 3D-Modelle. Entwickelt für moderne Ingenieurteams, die Präzision und Geschwindigkeit fordern.', es: 'Transforme bocetos 2D en modelos 3D listos para producción al instante. Creado para equipos de ingeniería modernos que exigen precisión y velocidad.' },
  startFree: { en: 'Start designing free', ko: '무료로 디자인 시작하기', ja: '無料でデザインを始める', zh: '免费开始设计', fr: 'Commencer à concevoir gratuitement', de: 'Kostenlos entwerfen', es: 'Empieza a diseñar gratis' },
  bookDemo: { en: 'Book a demo', ko: '데모 예약하기', ja: 'デモを予約する', zh: '预约演示', fr: 'Réserver une démo', de: 'Demo buchen', es: 'Reservar una demo' },
  bentoTitle: { en: 'Everything you need to build faster.', ko: '더 빠른 빌드를 위해 필요한 모든 것.', ja: '迅速な構築に必要なすべて。', zh: '快速构建所需的一切。', fr: 'Tout ce dont vous avez besoin pour construire plus vite.', de: 'Alles, was Sie brauchen, um schneller zu bauen.', es: 'Todo lo que necesitas para construir más rápido.' },
  bentoDesc: { en: 'A complete toolset designed to eliminate manual drafting and accelerate your product development cycle.', ko: '수동 제도를 없애고 제품 개발 주기를 가속화하도록 설계된 완벽한 툴셋입니다.', ja: '手作業による製図を排除し、製品開発サイクルを加速するために設計された完全なツールセット。', zh: '旨在消除手动绘图并加速产品开发周期的完整工具集。', fr: 'Un ensemble d\'outils complet conçu pour éliminer le dessin manuel et accélérer votre cycle de développement de produits.', de: 'Ein komplettes Toolset, das entwickelt wurde, um manuelles Zeichnen zu eliminieren und Ihren Produktentwicklungszyklus zu beschleunigen.', es: 'Un conjunto de herramientas completo diseñado para eliminar el dibujo manual y acelerar su ciclo de desarrollo de productos.' },
  card1Title: { en: 'AI-Powered Conversion', ko: 'AI 기반 변환', ja: 'AI駆動の変換', zh: 'AI 驱动转换', fr: 'Conversion optimisée par l\'IA', de: 'KI-gestützte Konvertierung', es: 'Conversión impulsada por IA' },
  card1Desc: { en: 'Upload any hand-drawn sketch or technical drawing. Our vision models instantly recognize dimensions, constraints, and geometry to generate a perfect 3D solid.', ko: '손으로 그린 스케치나 기술 도면을 업로드하세요. 비전 모델이 치수, 제약 조건, 기하학적 구조를 즉시 인식하여 완벽한 3D 솔리드를 생성합니다.', ja: '手描きのスケッチや技術図面をアップロードします。ビジョンモデルが寸法、制約、形状を即座に認識し、完璧な3Dソリッドを生成します。', zh: '上传任何手绘草图或技术图纸。我们的视觉模型会立即识别尺寸、约束和几何形状，以生成完美的 3D 实体。', fr: 'Téléchargez n\'importe quel croquis dessiné à la main ou dessin technique. Nos modèles de vision reconnaissent instantanément les dimensions, les contraintes et la géométrie pour générer un solide 3D parfait.', de: 'Laden Sie eine beliebige handgezeichnete Skizze oder technische Zeichnung hoch. Unsere Vision-Modelle erkennen sofort Abmessungen, Einschränkungen und Geometrie, um einen perfekten 3D-Körper zu generieren.', es: 'Sube cualquier boceto dibujado a mano o dibujo técnico. Nuestros modelos de visión reconocen instantáneamente dimensiones, restricciones y geometría para generar un sólido 3D perfecto.' },
  card2Title: { en: 'Real-time Rendering', ko: '실시간 렌더링', ja: 'リアルタイムレンダリング', zh: '实时渲染', fr: 'Rendu en temps réel', de: 'Echtzeit-Rendering', es: 'Renderizado en tiempo real' },
  card2Desc: { en: 'Physically based rendering directly in your browser.', ko: '브라우저에서 직접 물리 기반 렌더링을 제공합니다.', ja: 'ブラウザで直接物理ベースのレンダリングを行います。', zh: '直接在浏览器中进行基于物理的渲染。', fr: 'Rendu basé sur la physique directement dans votre navigateur.', de: 'Physikalisch basiertes Rendering direkt in Ihrem Browser.', es: 'Renderizado basado en la física directamente en tu navegador.' },
  card3Title: { en: 'Smart Constraints', ko: '스마트 제약 조건', ja: 'スマート制約', zh: '智能约束', fr: 'Contraintes intelligentes', de: 'Intelligente Einschränkungen', es: 'Restricciones inteligentes' },
  card3Desc: { en: 'Auto-detects parallel, perpendicular, and tangent relations.', ko: '평행, 수직, 접선 관계를 자동 감지합니다.', ja: '平行、垂直、接線関係を自動検出します。', zh: '自动检测平行、垂直和相切关系。', fr: 'Détecte automatiquement les relations parallèles, perpendiculaires et tangentes.', de: 'Erkennt automatisch parallele, senkrechte und tangentiale Beziehungen.', es: 'Detecta automáticamente relaciones paralelas, perpendiculares y tangentes.' },
  card4Title: { en: 'ISO Tolerances', ko: 'ISO 공차', ja: 'ISO公差', zh: 'ISO 公差', fr: 'Tolérances ISO', de: 'ISO-Toleranzen', es: 'Tolerancias ISO' },
  card4Desc: { en: 'Intelligent fit suggestions (H7, js6) based on context.', ko: '컨텍스트에 기반한 지능형 맞춤 제안 (H7, js6).', ja: 'コンテキストに基づくインテリジェントなはめあい提案（H7、js6）。', zh: '基于上下文的智能配合建议（H7、js6）。', fr: 'Suggestions d\'ajustement intelligentes (H7, js6) basées sur le contexte.', de: 'Intelligente Passungsvorschläge (H7, js6) basierend auf dem Kontext.', es: 'Sugerencias de ajuste inteligentes (H7, js6) basadas en el contexto.' },
  card5Title: { en: 'Export & Collaborate', ko: '내보내기 및 협업', ja: 'エクスポートとコラボレーション', zh: '导出与协作', fr: 'Exporter et collaborer', de: 'Exportieren & Zusammenarbeiten', es: 'Exportar y colaborar' },
  card5Desc: { en: 'Export directly to industry-standard formats like STEP and IGES. Seamlessly integrate with your existing manufacturing pipelines.', ko: 'STEP 및 IGES와 같은 업계 표준 형식으로 직접 내보냅니다. 기존 제조 파이프라인과 원활하게 통합됩니다.', ja: 'STEPやIGESなどの業界標準フォーマットに直接エクスポート。既存の製造パイプラインとシームレスに統合します。', zh: '直接导出为 STEP 和 IGES 等行业标准格式。与您现有的制造管道无缝集成。', fr: 'Exportez directement vers des formats standard de l\'industrie tels que STEP et IGES. Intégrez-vous de manière transparente à vos pipelines de fabrication existants.', de: 'Exportieren Sie direkt in branchenübliche Formate wie STEP und IGES. Nahtlose Integration in Ihre bestehenden Fertigungspipelines.', es: 'Exporte directamente a formatos estándar de la industria como STEP e IGES. Intégrelo perfectamente con sus líneas de fabricación existentes.' },
  footerRights: { en: '© 2026 GlowPoint Inc. All rights reserved.', ko: '© 2026 GlowPoint Inc. 모든 권리 보유.', ja: '© 2026 GlowPoint Inc. 無断複写・転載を禁じます。', zh: '© 2026 GlowPoint Inc. 保留所有权利。', fr: '© 2026 GlowPoint Inc. Tous droits réservés.', de: '© 2026 GlowPoint Inc. Alle Rechte vorbehalten.', es: '© 2026 GlowPoint Inc. Todos los derechos reservados.' },
  
  // Workspace
  project: { en: 'Project: Bracket_v1', ko: '프로젝트: Bracket_v1', ja: 'プロジェクト: Bracket_v1', zh: '项目：Bracket_v1', fr: 'Projet : Bracket_v1', de: 'Projekt: Bracket_v1', es: 'Proyecto: Bracket_v1' },
  simulateError: { en: 'Simulate Error', ko: '오류 시뮬레이션', ja: 'エラーをシミュレート', zh: '模拟错误', fr: 'Simuler une erreur', de: 'Fehler simulieren', es: 'Simular error' },
  fixError: { en: 'Fix Error', ko: '오류 수정', ja: 'エラーを修正', zh: '修复错误', fr: 'Corriger l\'erreur', de: 'Fehler beheben', es: 'Solucionar error' },
  versionHistory: { en: 'VERSION HISTORY', ko: '버전 기록', ja: 'バージョン履歴', zh: '版本历史', fr: 'HISTORIQUE DES VERSIONS', de: 'VERSIONSVERLAUF', es: 'HISTORIAL DE VERSIONES' },
  exportStep: { en: 'EXPORT TO STEP', ko: 'STEP으로 내보내기', ja: 'STEPへエクスポート', zh: '导出为 STEP', fr: 'EXPORTER VERS STEP', de: 'ALS STEP EXPORTIEREN', es: 'EXPORTAR A STEP' },
  view2d: { en: '2D SOURCE VIEW', ko: '2D 소스 뷰', ja: '2Dソースビュー', zh: '2D 源视图', fr: 'VUE SOURCE 2D', de: '2D-QUELLANSICHT', es: 'VISTA FUENTE 2D' },
  view3d: { en: '3D GENERATED SOLID', ko: '3D 생성 솔리드', ja: '3D生成ソリッド', zh: '3D 生成实体', fr: 'SOLIDE 3D GÉNÉRÉ', de: '3D-GENERIERTER KÖRPER', es: 'SÓLIDO 3D GENERADO' },
  autoConstraints: { en: 'Auto-detected constraints:', ko: '자동 감지된 제약 조건:', ja: '自動検出された制約:', zh: '自动检测到的约束：', fr: 'Contraintes détectées automatiquement :', de: 'Automatisch erkannte Einschränkungen:', es: 'Restricciones detectadas automáticamente:' },
  parallel: { en: 'Parallel', ko: '평행', ja: '平行', zh: '平行', fr: 'Parallèle', de: 'Parallel', es: 'Paralelo' },
  perpendicular: { en: 'Perpendicular', ko: '수직', ja: '垂直', zh: '垂直', fr: 'Perpendiculaire', de: 'Senkrecht', es: 'Perpendicular' },
  tangent: { en: 'Tangent', ko: '접선', ja: '接線', zh: '相切', fr: 'Tangente', de: 'Tangente', es: 'Tangente' },
  extrusionDepth: { en: 'Extrusion Depth', ko: '돌출 깊이', ja: '押し出し深さ', zh: '拉伸深度', fr: 'Profondeur d\'extrusion', de: 'Extrusionstiefe', es: 'Profundidad de extrusión' },
  apply: { en: 'Apply', ko: '적용', ja: '適用', zh: '应用', fr: 'Appliquer', de: 'Anwenden', es: 'Aplicar' },
  cancel: { en: 'Cancel', ko: '취소', ja: 'キャンセル', zh: '取消', fr: 'Annuler', de: 'Abbrechen', es: 'Cancelar' },
  processing: { en: 'Processing 2D geometry...', ko: '2D 지오메트리 처리 중...', ja: '2Dジオメトリを処理中...', zh: '正在处理 2D 几何图形...', fr: 'Traitement de la géométrie 2D...', de: '2D-Geometrie wird verarbeitet...', es: 'Procesando geometría 2D...' },
  generating: { en: 'Generating 3D solid...', ko: '3D 솔리드 생성 중...', ja: '3Dソリッドを生成中...', zh: '正在生成 3D 实体...', fr: 'Génération du solide 3D...', de: '3D-Körper wird generiert...', es: 'Generando sólido 3D...' },
  applying: { en: 'Applying constraints...', ko: '제약 조건 적용 중...', ja: '制約を適用中...', zh: '正在应用约束...', fr: 'Application des contraintes...', de: 'Einschränkungen werden angewendet...', es: 'Aplicando restricciones...' },
  ready: { en: 'Ready', ko: '준비 완료', ja: '準備完了', zh: '准备就绪', fr: 'Prêt', de: 'Bereit', es: 'Listo' },
  errorTitle: { en: 'Open loop detected.', ko: '열린 루프가 감지되었습니다.', ja: '開いたループが検出されました。', zh: '检测到开环。', fr: 'Boucle ouverte détectée.', de: 'Offene Schleife erkannt.', es: 'Bucle abierto detectado.' },
  errorDesc: { en: 'Please connect the lines to form a closed profile for extrusion.', ko: '돌출을 위한 닫힌 프로파일을 형성하려면 선을 연결하세요.', ja: '押し出し用の閉じたプロファイルを作成するには、線を接続してください。', zh: '请连接线条以形成用于拉伸的闭合轮廓。', fr: 'Veuillez connecter les lignes pour former un profil fermé pour l\'extrusion.', de: 'Bitte verbinden Sie die Linien, um ein geschlossenes Profil für die Extrusion zu bilden.', es: 'Conecte las líneas para formar un perfil cerrado para la extrusión.' },
  hole: { en: 'Hole', ko: '구멍', ja: '穴', zh: '孔', fr: 'Trou', de: 'Loch', es: 'Agujero' },
  shaft: { en: 'Shaft', ko: '축', ja: 'シャフト', zh: '轴', fr: 'Arbre', de: 'Welle', es: 'Eje' },
  transition: { en: 'Transition', ko: '전환', ja: '遷移', zh: '过渡', fr: 'Transition', de: 'Übergang', es: 'Transición' },
  custom: { en: 'Custom', ko: '사용자 정의', ja: 'カスタム', zh: '自定义', fr: 'Personnalisé', de: 'Benutzerdefiniert', es: 'Personalizado' },
};

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string) => string;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>('en');

  const t = (key: string) => {
    return translations[key]?.[language] || key;
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}
