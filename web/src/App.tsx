
import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { tools, ToolCategory } from './config/tools';
import ToolCard from './components/ToolCard';
import { ActivePanel } from './components/ActivePanel';
import './App.css';

function App() {
  const [activeToolId, setActiveToolId] = useState<string | null>("merge-pptx");
  const [filter, setFilter] = useState<ToolCategory | 'all'>('all');
  const [search, setSearch] = useState('');

  const activeTool = useMemo(() => tools.find(t => t.id === activeToolId), [activeToolId]);

  const filteredTools = useMemo(() => {
    return tools.filter(t => {
      const matchesCategory = filter === 'all' || t.category === filter;
      const matchesSearch = t.title.toLowerCase().includes(search.toLowerCase()) || 
                          t.description.toLowerCase().includes(search.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [filter, search]);

  const categories: { id: ToolCategory | 'all', label: string }[] = [
    { id: 'all', label: 'All Tools' },
    { id: 'ai', label: '🤖 AI Tools' },
    { id: 'pptx', label: 'PowerPoint' },
    { id: 'organize', label: 'Organize PDF' },
    { id: 'convert', label: 'Convert' },
    { id: 'extract', label: 'Extract' },
    { id: 'edit', label: 'Edit' },
    { id: 'security', label: 'Security' },
    { id: 'optimize', label: 'Optimize' },
  ];

  return (
    <div className="min-h-screen pb-20">
      {/* Background Orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] rounded-full bg-primary/20 blur-[100px] animate-blob" />
        <div className="absolute bottom-[-10%] left-[-10%] w-[600px] h-[600px] rounded-full bg-secondary/15 blur-[120px] animate-blob animation-delay-2000" />
        <div className="absolute top-[40%] left-[20%] w-[300px] h-[300px] rounded-full bg-accent/15 blur-[80px] animate-blob animation-delay-4000" />
      </div>

      <header className="sticky top-0 z-10 py-3 px-4 md:px-6 backdrop-blur-xl bg-background/80 border-b border-white/10">
        <div className="max-w-7xl mx-auto flex flex-row gap-4 justify-between items-center">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center font-bold text-black text-lg shadow-lg">A</div>
          <div>
            <h1 className="text-xl md:text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-200 via-white to-orange-200">
              AsFiles
            </h1>
            <p className="text-xs text-gray-400 hidden sm:block">PDF & PowerPoint tools</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
            {/* Search */}
            <div className="relative">
                <input 
                    type="text" 
                    placeholder="Search..." 
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="bg-white/10 border border-white/20 rounded-full px-4 py-2 pl-9 w-40 md:w-56 text-sm focus:outline-none focus:border-cyan-400/70 focus:w-64 md:focus:w-72 transition-all duration-300 backdrop-blur-md hover:border-white/40"
                />
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔍</span>
            </div>
            
            <a href="https://github.com" target="_blank" className="p-2 rounded-full bg-white/5 hover:bg-white/15 transition-all duration-300 border border-white/10 hover:border-white/30">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd"></path></svg>
            </a>
        </div>
        </div>
      </header>

      <main className="relative z-10 max-w-7xl mx-auto px-6">
        
        {/* Active Tool Panel */}
        <AnimatePresence mode="wait">
          {activeTool ? (
            <motion.div
              key={activeTool.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
              className="mb-16"
            >
              <button 
                onClick={() => setActiveToolId(null)}
                className="sticky top-16 z-20 mb-6 flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-300 hover:text-white bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-full transition-all duration-200 backdrop-blur-md shadow-lg"
              >
                <span>←</span> Back to All Tools
              </button>
              <ActivePanel tool={activeTool} />
            </motion.div>
          ) : (
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
            >
                 {/* Category Filters */}
                <motion.div 
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex flex-wrap gap-2 justify-center mb-12"
                >
                  {categories.map((cat, idx) => (
                    <motion.button
                      key={cat.id}
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: idx * 0.05 }}
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => setFilter(cat.id)}
                      className={`
                        px-5 py-2.5 rounded-full text-sm font-semibold transition-all duration-300 border backdrop-blur-md shadow-lg
                        ${filter === cat.id 
                          ? 'bg-gradient-to-r from-cyan-400 to-blue-500 text-black border-cyan-300 shadow-xl shadow-cyan-500/40' 
                          : 'bg-white/5 text-gray-300 border-white/20 hover:bg-white/10 hover:text-white hover:border-white/40 hover:shadow-xl hover:shadow-white/10'}
                      `}
                    >
                      {cat.label}
                    </motion.button>
                  ))}
                </motion.div>

                {/* Grid with visual hierarchy */}
                <motion.div 
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.2 }}
                  className="grid grid-cols-1 md:grid-cols-12 gap-6 pb-20"
                >
                  {filteredTools.map((tool, idx) => {
                    const isPrimary = tool.id === 'merge-pptx';
                    const colClass = isPrimary ? 'md:col-span-6 xl:col-span-6' : 'md:col-span-4 xl:col-span-3';
                    return (
                      <motion.div
                        key={tool.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: idx * 0.05 }}
                        className={colClass}
                      >
                        <ToolCard
                          tool={tool}
                          isActive={activeToolId === tool.id}
                          onClick={() => {
                              setActiveToolId(tool.id);
                              window.scrollTo({ top: 0, behavior: 'smooth' });
                          }}
                        />
                      </motion.div>
                    );
                  })}
                </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

      </main>
    </div>
  );
}

export default App;
