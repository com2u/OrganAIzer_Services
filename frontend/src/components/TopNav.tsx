/**
 * Top navigation bar component.
 * Displays the application logo/title and navigation links.
 * Designed to accommodate multiple tools as the application grows.
 */

export default function TopNav() {
  return (
    <nav className="bg-blue-600 text-white shadow-md">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold">OrganAIzer Services</h1>
          </div>
          
          <div className="flex space-x-6">
            <a 
              href="#" 
              className="hover:text-blue-200 transition-colors font-medium border-b-2 border-white pb-1"
            >
              Text-to-Speech
            </a>
            {/* Future tools will be added here as navigation items */}
          </div>
        </div>
      </div>
    </nav>
  );
}
