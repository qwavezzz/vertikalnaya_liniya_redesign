(function () {
    const accepted = localStorage.getItem('qformCookiesAccepted');
    if (accepted === 'true') return;

    const defaults = {
        backgroundColor: '#ffffff',
        buttonColor: '#07b859',
        shadowColor: '#aaa',
        fontSize: '14px',
        display: 'inline-block',
        lineHeight: '100%',
        position: 'bottom-left',
        privacyLink: '/politika-konfidentsialnosti-sajta',
        cookieExpiryDays: 365,
        language: 'ru' // ru / en
    };

    const settings = window.qformCookieSettings || {};
    const config = { ...defaults, ...settings };

    const defaultTexts = {
        message: `Мы обрабатываем cookies, чтобы пользоваться сайтом было удобнее. Вы можете запретить обработку cookies в настройках браузера. Пожалуйста, ознакомьтесь с `,
        policy: 'политикой конфиденциальности',
        acceptBtn: 'Принять'
    };
    
    const message = config.messageText || defaultTexts.message;
    const policy = config.policyText || defaultTexts.policy;
    const acceptBtn = config.acceptButtonText || defaultTexts.acceptBtn;

    const banner = document.createElement('div');
    banner.id = 'qformCookieBanner';

    let translateX = '', translateY = '';
    switch (config.position) {
        case 'top':
            banner.style.top = '20px';
            banner.style.right = '20px';
            banner.style.left = '20px';
            banner.style.margin = 'auto';
            break;
        case 'bottom':
            banner.style.bottom = '20px';
            banner.style.right = '20px';
            banner.style.left = '20px';
            banner.style.margin = 'auto';
            break;
        case 'bottom-right':
            banner.style.right = '20px';
            banner.style.bottom = '20px';
            break;
        case 'bottom-left':
            banner.style.left = '20px';
            banner.style.right = '20px';
            banner.style.bottom = '20px';
            break;
        case 'top-right':
            banner.style.right = '20px';
            banner.style.top = '20px';
            break;
        case 'top-left':
            banner.style.left = '20px';
            banner.style.top = '20px';
            break;
        default:
            banner.style.right = '20px';
            banner.style.bottom = '20px';
    }

    banner.style.position = 'fixed';
    banner.style.backgroundColor = config.backgroundColor;
    banner.style.boxShadow = `0 4px 10px ${config.shadowColor}`;
    banner.style.padding = '15px';
    banner.style.borderRadius = '8px';
    banner.style.maxWidth = '840px';
    banner.style.zIndex = '9999';
    banner.style.fontFamily = 'inherit';
    banner.style.fontSize = config.fontSize;
    banner.style.lineHeight = config.lineHeight;
    banner.style.display = 'inline-block';
    banner.style.flexDirection = 'column';
    banner.style.gap = '10px';
    banner.style.opacity = '0';
    banner.style.transition = 'opacity 0.5s ease-in-out';
    banner.style.animation = 'slideIn 0.5s ease forwards';
    banner.style.transform = 'none';

    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: ${
                    config.position === 'top'
                        ? 'translate(0, -20px)'
                        : config.position === 'top-right'
                        ? 'translate(20px, -20px)'
                        : config.position === 'top-left'
                        ? 'translate(-20px, -20px)'
                        : config.position === 'bottom-right'
                        ? 'translate(20px, 20px)'
                        : config.position === 'bottom-left' 
                        ? 'translate(-20px, 20px)'
                        : 'translate(0, 20px)'
                };
            }
            to {
                opacity: 1;
                transform: translate(0, 0);
            }
        }
    `;
    document.head.appendChild(style);

    banner.innerHTML = `
        <div class="cookie0" style="">${message} <a href="${config.privacyLink}" target="_blank" style="color: ${config.buttonColor}; text-decoration: underline;">${policy}</a></div>
        
        <button id="qformAcceptCookies" style="
            background-color: ${config.buttonColor};
            border: none;
            float: right;
            display: inline-block;
            color: white;
            padding: 10px 15px;
            font-size: ${config.fontSize};
            border-radius: 5px;
            cursor: pointer;
            align-self: flex-start;
        ">${acceptBtn}</button>
        
    `;

    document.body.appendChild(banner);

    setTimeout(() => {
        banner.style.opacity = '1';
    }, 100);

    document.getElementById('qformAcceptCookies').addEventListener('click', () => {
        localStorage.setItem('qformCookiesAccepted', 'true');

        banner.style.opacity = '0';
        setTimeout(() => {
            document.body.removeChild(banner);
        }, 500);
    });
})();