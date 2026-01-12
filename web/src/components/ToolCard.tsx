
import { motion } from "framer-motion";
import { Tool } from "../config/tools";
import * as LucideIcons from "lucide-react";
import { LucideIcon } from "lucide-react";

interface ToolCardProps {
  tool: Tool;
  isActive: boolean;
  onClick: () => void;
}

const ToolCard = ({ tool, isActive, onClick }: ToolCardProps) => {
  const isPriority = tool.tag?.toLowerCase() === "priority";
  // Dynamically get the Lucide icon component
  const IconComponent = (LucideIcons as unknown as Record<string, LucideIcon>)[tool.icon] || LucideIcons.File;

  return (
    <motion.button
      whileHover={{ y: -6, scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className="w-full h-full group relative"
    >
      {/* Main card */}
      <div
        className={
          `relative z-10 h-full flex flex-col gap-4 p-6 rounded-2xl text-left
           transition-all duration-300 overflow-hidden border backdrop-blur-xl
           ${isActive ? 'border-white/30 bg-white/10 shadow-2xl' : 'border-white/15 bg-white/5 hover:border-white/25 hover:bg-white/8 hover:shadow-2xl'}
           ${isPriority ? 'ring-1 ring-amber-400/40 shadow-glow' : ''}`
        }
      >
        {/* Top section with icon and tag */}
        <div className="relative z-20 flex justify-between items-start">
          {/* Icon container using Tailwind gradient */}
          <motion.div
            whileHover={{ scale: 1.06 }}
            className={
              `relative w-14 h-14 rounded-xl flex items-center justify-center shadow-lg overflow-hidden
               bg-gradient-to-br ${tool.accent}`
            }
          >
            <IconComponent className="text-white" size={26} />
          </motion.div>

          {/* Tag */}
          {tool.tag && (
            <motion.span
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="text-[10px] font-bold px-2.5 py-1 rounded-full text-black tracking-wider uppercase bg-gradient-to-r from-amber-400 to-amber-500 shadow-md"
            >
              {tool.tag}
            </motion.span>
          )}
        </div>

        {/* Title and description */}
        <div className="relative z-20 flex-grow">
          <h3 className="font-bold text-lg mb-2 bg-clip-text text-transparent bg-gradient-to-r from-white to-white/80">
            {tool.title}
          </h3>
          <p className="text-sm text-gray-300 leading-relaxed">
            {tool.description}
          </p>
        </div>

        {/* Bottom section */}
        <div className="relative z-20 mt-auto pt-4 flex items-center justify-between border-t border-white/10">
          {/* Status dot without noisy text */}
          <div className="flex items-center gap-2">
            <span className={`inline-block w-2.5 h-2.5 rounded-full ${tool.status === 'ready' ? 'bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.6)]' : 'bg-gray-500'}`} />
            <span className="text-xs text-gray-400">{tool.status === 'ready' ? 'Live' : 'Queued'}</span>
          </div>
          <motion.span
            className="text-white/70 group-hover:text-white transition-all duration-300 font-bold text-lg"
            initial={{ x: 0, opacity: 0 }}
            whileHover={{ x: 4, opacity: 1 }}
          >
            →
          </motion.span>
        </div>
      </div>
    </motion.button>
  );
};

export default ToolCard;


