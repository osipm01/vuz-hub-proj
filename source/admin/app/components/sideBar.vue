<style>
    /* Анимация плавного возвращения сайдбара на место */
    @keyframes sidebarSlideIn {
        100% {
            opacity: 1;
            transform: translateX(0);
        }
    }

    /* Анимация проявления элементов внутри сайдбара */
    @keyframes elementFadeIn {
        100% {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* Специальная анимация для ссылок */
    @keyframes linkSlideIn {
        100% {
            opacity: 1;
            transform: translateX(0);
        }
    }

    .sidebar {
        min-width: 250px;
        min-height: 90vh;
        max-height: 100vh;
        border: 1px solid #fff;
        border-radius: 15px;
        padding: 16px;
        box-shadow: 12px 0px 50px 0px rgba(34, 60, 80, 0.3);
        transition: box-shadow ease-in-out .3s, max-width ease-in-out .5s;
        display: flex;
        flex-direction: column;
        justify-content: space-between;

        /* ХАРДКОД НАЧАЛЬНОГО СОСТОЯНИЯ: прячем сайдбар влево ДО старта анимации */
        opacity: 0;
        transform: translateX(-100%);

        /* Запуск анимации */
        animation: sidebarSlideIn 0.7s cubic-bezier(0.25, 1, 0.5, 1) forwards;
    }

    /* ХАРДКОД НАЧАЛЬНОГО СОСТОЯНИЯ для внутренних элементов */
    .profile_containner, button {
        opacity: 0;
        transform: translateY(15px);
        animation: elementFadeIn 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
    }

    /* Каскадная задержка появления базовых блоков */
    .profile_containner {
        animation-delay: 0.3s;
    }

    /* ХАРДКОД НАЧАЛЬНОГО СОСТОЯНИЯ для ссылок */
    .link_blok a {
        opacity: 0;
        transform: translateX(-20px);
        animation: linkSlideIn 0.5s cubic-bezier(0.25, 1, 0.5, 1) forwards;
    }

    /* Эффект домино для ссылок */
    .link_blok a:nth-child(1) { animation-delay: 0.45s; }
    .link_blok a:nth-child(2) { animation-delay: 0.55s; }
    .link_blok a:nth-child(3) { animation-delay: 0.65s; }

    /* Кнопка идет в самом конце */
    button {
        animation-delay: 0.8s;
    }

    button {
        box-shadow: 12px 0px 50px 0px rgba(34, 60, 80, 0.3);
        border: 1px solid #fff;
        border-radius: 15px;
        padding: 12px;
        cursor: pointer;
        background: transparent;
        /* Убрали transform из общего transition, чтобы не ломать анимацию */
        transition: box-shadow ease-out .3s, background-color ease-out .3s, transform ease-out .1s;
        color: aliceblue;
    }

    button:hover {
        box-shadow: 12px 4px 25px 0px rgba(34, 60, 80, 0.4);
        transform: scale(1.03) !important; /* !important защищает масштаб при ховере */
        background-color: rgba(255, 255, 255, 0.1);
    }

    button:active {
        transform: scale(0.98) !important;
    }

    .sidebar:hover {
        box-shadow: 32px 0px 50px 0px rgba(34, 60, 80, 0.3);
    }

    .profile_containner {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        justify-content: center;
        gap: 8px;
        color: aliceblue;
    }

    .link_blok {
        width: 100%;
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin: 20px 0;
    }

    /* Ссылки */
    a {
        text-decoration: none;
        color: aliceblue;
        font-size: 15px;
        padding: 10px 14px;
        border-radius: 10px;
        border: 1px solid transparent;
        display: flex;
        align-items: center;
        transition: background-color 0.3s ease, border-color 0.3s ease, padding-left 0.3s ease, transform 0.2s ease;
    }

    a:hover {
        background-color: rgba(255, 255, 255, 0.15);
        border-color: rgba(255, 255, 255, 0.25);
        padding-left: 20px;
        transform: translateX(4px) !important;
    }

    a:active {
        transform: translateX(2px) scale(0.98) !important;
    }

    span {
        font-size: 17px;
    }

    @media (max-width: 300px) {
        .sidebar {
            max-width: 75px;
        }
        a {
            padding: 10px 8px;
            font-size: 12px;
        }
        a:hover {
            padding-left: 10px;
            transform: none !important;
        }
    }
</style>




<template>
  <div class="sidebar">
    <div class="profile_containner">
      <span>1</span>
      <span>2</span>
      <span>3</span>
    </div>

    <div class="link_blok">
      <NuxtLink to="/">главная</NuxtLink>
      <NuxtLink to="/users">пользователи</NuxtLink>
      <NuxtLink to="/media">медиа-ресурсы</NuxtLink>
    </div>

    <button @click="handleLogoutBtn">logout(выйти)</button>
  </div>
</template>

<script setup lang="ts">
// если добавлял computed в хук — можно так:
// const { logOut, userName, userRole, userId, fetchMe } = useAuth()

// На случай SSR/hard reload — подтянуть актуальные данные с бэка
// onMounted(() => {
//   fetchMe().catch(() => {})
// })

const handleLogoutBtn = async () => {
  // await logOut()
  return navigateTo('/auth')
}
</script>
