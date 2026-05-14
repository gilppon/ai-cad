import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

export default function Landing() {
  return (
    <div className="min-h-screen bg-base overflow-hidden">
      {/* Navbar (Glass) */}
      <nav className="fixed top-0 left-0 w-full z-50 px-8 py-6 flex justify-between items-center mix-blend-difference text-white">
        <div className="font-outfit font-light text-2xl tracking-widest">
          kodari<span className="font-medium">.ai</span>
        </div>
        <div className="flex gap-8 text-sm font-outfit uppercase tracking-widest">
          <a href="#about" className="hover:opacity-70 transition">About</a>
          <a href="#services" className="hover:opacity-70 transition">Services</a>
          <Link to="/login" className="hover:opacity-70 transition">Client Login</Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative h-[90vh] w-full p-4">
        <div className="w-full h-full rounded-3xl overflow-hidden relative shadow-2xl">
          {/* Background Image */}
          <div 
            className="absolute inset-0 bg-cover bg-center transform hover:scale-105 transition-transform duration-[10s] ease-out"
            style={{ backgroundImage: "url('/hero-architecture.png')" }}
          ></div>
          
          {/* Overlay */}
          <div className="absolute inset-0 bg-black/10"></div>

          {/* Hero Content */}
          <div className="absolute inset-0 flex flex-col justify-center px-16 lg:px-32 animate-fade-in-up">
            <h1 className="text-white text-7xl lg:text-9xl font-outfit font-extralight tracking-tighter leading-none">
              smart<br />
              <span className="font-normal pl-24">ifc.vision</span>
            </h1>
          </div>

          {/* Glass floating stats */}
          <div className="absolute bottom-12 right-12 flex gap-4 animate-fade-in-up" style={{ animationDelay: '0.3s' }}>
            <div className="glass-panel rounded-2xl p-6 text-white w-40">
              <p className="text-4xl font-display mb-1">99.9%</p>
              <p className="text-xs font-outfit uppercase tracking-wider opacity-80">AI Recognition Precision</p>
            </div>
            <div className="glass-panel rounded-2xl p-6 text-white w-40">
              <p className="text-4xl font-display mb-1">&lt; 10s</p>
              <p className="text-xs font-outfit uppercase tracking-wider opacity-80">IFC Conversion Speed</p>
            </div>
          </div>
          
          {/* Action pill */}
          <div className="absolute bottom-8 left-1/2 -translate-x-1/2 glass-panel rounded-full px-8 py-3 text-white flex items-center gap-4 cursor-pointer hover:bg-white/30 transition">
            <span className="text-sm font-outfit uppercase tracking-widest">Contact Us</span>
            <div className="w-8 h-8 rounded-full bg-accent/80 flex items-center justify-center">
              <ArrowRight size={16} />
            </div>
          </div>
        </div>
      </section>

      {/* About Us Section */}
      <section id="about" className="py-32 px-16 lg:px-32 max-w-7xl mx-auto flex flex-col md:flex-row gap-16">
        <div className="md:w-1/2">
          <h2 className="text-6xl lg:text-8xl font-outfit font-extralight tracking-tighter text-charcoal mb-8 animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
            about <span className="font-normal">us</span>
          </h2>
          
          <div className="flex gap-4 mt-16 animate-fade-in-up" style={{ animationDelay: '0.4s' }}>
            <img src="/detail-architecture.png" alt="Detail 1" className="w-32 h-24 object-cover rounded-xl shadow-lg" />
            <img src="/hero-architecture.png" alt="Detail 2" className="w-32 h-24 object-cover rounded-xl shadow-lg opacity-70" />
          </div>
        </div>
        
        <div className="md:w-1/2 flex items-center">
          <p className="text-lg lg:text-2xl font-outfit font-light leading-relaxed text-charcoal/80 animate-fade-in-up" style={{ animationDelay: '0.3s' }}>
            <span className="text-accent font-medium uppercase text-sm tracking-widest block mb-4">Revolutionizing BIM</span>
            AI-POWERED ARCHITECTURAL ANALYSIS THAT TRANSFORMS 2D PDF FLOOR PLANS INTO INTELLIGENT 3D IFC MODELS IN SECONDS. WE BRIDGE THE GAP BETWEEN PAPER AND DIGITAL TWIN.
          </p>
        </div>
      </section>

      {/* Call to Action CTA */}
      <section className="py-24 border-t border-charcoal/10 flex justify-center">
        <Link 
          to="/login"
          className="group relative inline-flex items-center justify-center px-12 py-6 text-lg font-outfit uppercase tracking-widest overflow-hidden rounded-full bg-charcoal text-white hover:bg-accent transition duration-500"
        >
          <span>Start Your Project</span>
          <ArrowRight className="ml-4 transform group-hover:translate-x-2 transition" />
        </Link>
      </section>
    </div>
  );
}
