import { Outlet, NavLink, useNavigate } from 'react-router-dom'

export default function Layout() {
  const navigate = useNavigate()

  const logout = () => {
    localStorage.removeItem('token')
    navigate('/login')
  }

  return (
    <div className="min-h-screen flex bg-gray-50">
      <aside className="w-56 bg-white border-r border-gray-200 flex flex-col">
        <div className="px-5 py-4 border-b border-gray-200">
          <h1 className="text-lg font-bold text-blue-700">SkemaBygger</h1>
        </div>
        <nav className="flex-1 p-3 space-y-1 text-sm">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `block px-3 py-2 rounded-md font-medium ${isActive ? 'bg-blue-50 text-blue-700' : 'text-gray-700 hover:bg-gray-100'}`
            }
          >
            Skoler
          </NavLink>
          <NavLink
            to="/tokens"
            className={({ isActive }) =>
              `block px-3 py-2 rounded-md font-medium ${isActive ? 'bg-blue-50 text-blue-700' : 'text-gray-700 hover:bg-gray-100'}`
            }
          >
            Adgangstokens
          </NavLink>
        </nav>
        <button
          onClick={logout}
          className="m-3 px-3 py-2 text-sm text-gray-500 hover:text-gray-800 text-left rounded-md hover:bg-gray-100"
        >
          Log ud
        </button>
      </aside>
      <main className="flex-1 p-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
