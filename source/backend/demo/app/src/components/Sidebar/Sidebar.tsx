import { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './Sidebar.css';

export default function Sidebar() {
  // const { logOut, userName, userRole, userId, fetchMe } = useAuth();
  const navigate = useNavigate();


  return (
    <div className="sidebar">
      <div className="profile_containner">
        <span>user</span>
        <span>user</span>
        <span>user</span>
      </div>

      <div className="link_blok">
        <Link to="/">главная</Link>
        <Link to="/users">пользователи</Link>
        <Link to="/media">медиа-ресурсы</Link>
      </div>

      <button>logout(выйти)</button>
    </div>
  );
}
