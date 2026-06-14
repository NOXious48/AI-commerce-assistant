import React from 'react';
import { Link } from 'react-router-dom';

interface SubItem {
  title: string;
  image: string;
  link: string;
}

interface CategoryCardProps {
  title: string;
  items: SubItem[];
  footerText?: string;
  footerLink?: string;
}

export default function CategoryCard({ title, items, footerText, footerLink }: CategoryCardProps) {
  return (
    <div className="bg-white p-4 flex flex-col h-full border border-gray-100 shadow-sm relative z-20">
      <h2 className="text-xl font-bold text-gray-900 mb-4 line-clamp-2 min-h-[56px] leading-tight">
        {title}
      </h2>
      
      <div className="flex-1 grid grid-cols-2 gap-x-4 gap-y-6">
        {items.map((item, idx) => (
          <Link to={item.link} key={idx} className="flex flex-col group cursor-pointer">
            <div className="bg-gray-50 aspect-square mb-2 flex items-center justify-center overflow-hidden">
              <img 
                src={item.image} 
                alt={item.title} 
                className="w-full h-full object-cover mix-blend-multiply group-hover:scale-105 transition-transform duration-300"
              />
            </div>
            <span className="text-xs text-gray-800 line-clamp-1 group-hover:text-orange-600 transition-colors">
              {item.title}
            </span>
          </Link>
        ))}
      </div>
      
      {footerText && (
        <div className="mt-6">
          <Link to={footerLink || "#"} className="text-sm text-blue-600 hover:text-orange-600 hover:underline">
            {footerText}
          </Link>
        </div>
      )}
    </div>
  );
}
