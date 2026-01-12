
import { FormFieldConfig } from "../../config/tools";
import { cn } from "./Button";

interface FormFieldProps {
  field: FormFieldConfig;
  value: string | number | boolean;
  onChange: (name: string, value: string | number | boolean) => void;
}

export const FormField = ({ field, value, onChange }: FormFieldProps) => {
  const id = `field-${field.name}`;

  const baseInputStyles = "w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all placeholder:text-gray-600";
  const labelStyles = "block text-xs font-medium text-gray-400 mb-1.5 ml-1";

  switch (field.type) {
    case "select":
      return (
        <div>
          <label htmlFor={id} className={labelStyles}>{field.label}</label>
          <div className="relative">
            <select
              id={id}
              value={String(value)}
              onChange={(e) => onChange(field.name, e.target.value)}
              className={cn(baseInputStyles, "appearance-none cursor-pointer")}
            >
              {field.options?.map((opt) => (
                <option key={opt.value} value={opt.value} className="bg-slate-900 text-white">
                  {opt.label}
                </option>
              ))}
            </select>
            <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-gray-500 text-xs">
              ▼
            </div>
          </div>
        </div>
      );
    
    case "checkbox":
      return (
        <div className="flex items-center gap-3 p-3 rounded-lg border border-white/5 hover:bg-white/5 transition-colors cursor-pointer" onClick={() => onChange(field.name, !value)}>
          <div className={cn(
            "w-5 h-5 rounded flex items-center justify-center transition-colors",
            value ? "bg-primary text-white" : "bg-black/20 border border-white/20"
          )}>
            {value && "✓"}
          </div>
          <span className="text-sm font-medium text-gray-300 select-none">{field.label}</span>
        </div>
      );
    
    case "range":
      return (
        <div>
          <div className="flex justify-between items-center mb-2">
            <label htmlFor={id} className={labelStyles}>{field.label}</label>
            <span className="text-xs bg-white/10 px-2 py-0.5 rounded text-gray-300">
              {value}
            </span>
          </div>
          <input
            id={id}
            type="range"
            min={field.min}
            max={field.max}
            step={field.step}
            value={Number(value)}
            onChange={(e) => onChange(field.name, parseFloat(e.target.value))}
            className="w-full h-2 bg-black/30 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary hover:[&::-webkit-slider-thumb]:bg-primary/80"
          />
        </div>
      );
    
    default:
      return (
        <div>
          <label htmlFor={id} className={labelStyles}>{field.label}</label>
          <input
            id={id}
            type={field.type}
            value={String(value)}
            placeholder={field.placeholder}
            required={field.required}
            onChange={(e) => onChange(field.name, e.target.value)}
            className={baseInputStyles}
          />
        </div>
      );
  }
};
