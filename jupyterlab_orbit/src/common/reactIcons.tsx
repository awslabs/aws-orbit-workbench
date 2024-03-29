// EXTRACTED FROM https://react-svgr.com/playground/?typescript=true

import React from 'react';
import Icon from '@ant-design/icons';
import { v4 } from 'uuid';

const ec2Svg = () => {
  const gradientId = v4();
  return (
    <svg width="40px" height="40px" viewBox="0 0 40 40">
      <defs>
        <linearGradient x1="0%" y1="100%" x2="100%" y2="0%" id={gradientId}>
          <stop stopColor="#C8511B" offset="0%" />
          <stop stopColor="#FF9900" offset="100%" />
        </linearGradient>
      </defs>
      <g stroke="none" strokeWidth="1" fill="none" fillRule="evenodd">
        <g fill={'url(#' + gradientId + ')'}>
          <rect x="0" y="0" width="40" height="40" />
        </g>
        <path
          d="M26.052,27 L26,13.948 L13,14 L13,27.052 L26.052,27 Z M27,14 L29,14 L29,15 L27,15 L27,17 L29,17 L29,18 L27,18 L27,20 L29,20 L29,21 L27,21 L27,23 L29,23 L29,24 L27,24 L27,26 L29,26 L29,27 L27,27 L27,27.052 C27,27.575 26.574,28 26.052,28 L26,28 L26,30 L25,30 L25,28 L23,28 L23,30 L22,30 L22,28 L20,28 L20,30 L19,30 L19,28 L17,28 L17,30 L16,30 L16,28 L14,28 L14,30 L13,30 L13,28 L12.948,28 C12.426,28 12,27.575 12,27.052 L12,27 L10,27 L10,26 L12,26 L12,24 L10,24 L10,23 L12,23 L12,21 L10,21 L10,20 L12,20 L12,18 L10,18 L10,17 L12,17 L12,15 L10,15 L10,14 L12,14 L12,13.948 C12,13.425 12.426,13 12.948,13 L13,13 L13,11 L14,11 L14,13 L16,13 L16,11 L17,11 L17,13 L19,13 L19,11 L20,11 L20,13 L22,13 L22,11 L23,11 L23,13 L25,13 L25,11 L26,11 L26,13 L26.052,13 C26.574,13 27,13.425 27,13.948 L27,14 Z M21,33 L7,33 L7,19 L9,19 L9,18 L7.062,18 C6.477,18 6,18.477 6,19.062 L6,32.938 C6,33.523 6.477,34 7.062,34 L20.939,34 C21.524,34 22,33.523 22,32.938 L22,31 L21,31 L21,33 Z M34,7.062 L34,20.938 C34,21.523 33.524,22 32.939,22 L30,22 L30,21 L33,21 L33,7 L19,7 L19,10 L18,10 L18,7.062 C18,6.477 18.477,6 19.062,6 L32.939,6 C33.524,6 34,6.477 34,7.062 L34,7.062 Z"
          fill="#FFFFFF"
        />
      </g>
    </svg>
  );
};

const fargateIcon = () => {
  const gradientId = v4();
  return (
    <svg width="40px" height="40px" viewBox="0 0 40 40" version="1.1">
      <title>Icon-Architecture/32/Arch_AWS-Fargate_32</title>
      <desc>Created with Sketch.</desc>
      <defs>
        <linearGradient x1="0%" y1="100%" x2="100%" y2="0%" id={gradientId}>
          <stop stopColor="#C8511B" offset="0%" />
          <stop stopColor="#FF9900" offset="100%" />
        </linearGradient>
      </defs>
      <g
        id="Icon-Architecture/32/Arch_AWS-Fargate_32"
        stroke="none"
        strokeWidth="1"
        fill="none"
        fillRule="evenodd"
      >
        <g
          id="Icon-Architecture-BG/32/Containers"
          fill={'url(#' + gradientId + ')'}
        >
          <rect id="Rectangle" x="0" y="0" width="40" height="40" />
        </g>
        <path
          d="M26.8732809,29.3426248 L26.8732809,25.9139741 L28.8408644,25.248207 L28.8408644,28.6339372 L26.8732809,29.3426248 Z M23.9292731,28.0080961 L23.9292731,25.248207 L25.8909627,25.912976 L25.8909627,29.3426248 L23.9292731,28.6339372 L23.9292731,28.0080961 Z M22.9469548,32.0865434 L20.9793713,32.7942329 L20.9793713,29.3665804 L22.9469548,28.7008133 L22.9469548,28.9862847 L22.9469548,32.0865434 Z M18.0353635,28.9862847 L18.0353635,28.7008133 L19.997053,29.3655823 L19.997053,32.7942329 L18.0353635,32.0865434 L18.0353635,28.9862847 Z M15.0854617,29.3426248 L15.0854617,25.9139741 L17.0530452,25.248207 L17.0530452,28.0080961 L17.0530452,28.6339372 L15.0854617,29.3426248 Z M12.1414538,25.248207 L14.1031434,25.912976 L14.1031434,29.3426248 L12.1414538,28.6339372 L12.1414538,25.248207 Z M14.5943026,24.0733826 L15.9980354,24.5534935 L14.5943026,25.0286137 L13.1935167,24.5534935 L14.5943026,24.0733826 Z M20.4882122,27.5249908 L21.891945,28.0051017 L20.4882122,28.4802218 L19.0874263,28.0051017 L20.4882122,27.5249908 Z M26.3821218,24.0733826 L27.7858546,24.5534935 L26.3821218,25.0286137 L24.981336,24.5534935 L26.3821218,24.0733826 Z M29.4882122,24.0833641 L26.5383104,23.0732348 C26.4371316,23.0382994 26.3261297,23.0382994 26.2249509,23.0732348 L23.280943,24.0833641 C23.0815324,24.1522366 22.9479371,24.3418854 22.9469548,24.556488 L22.9469548,27.3133826 L20.6444008,26.525841 C20.543222,26.4909057 20.43222,26.4909057 20.3310413,26.525841 L18.0353635,27.3133826 L18.0353635,24.556488 C18.0343811,24.3418854 17.9007859,24.1512384 17.7003929,24.0833641 L14.7504912,23.0732348 C14.6493124,23.0382994 14.5383104,23.0382994 14.4371316,23.0732348 L11.4931238,24.0833641 C11.2937132,24.1522366 11.1601179,24.3418854 11.1591356,24.556488 L11.1591356,28.9862847 C11.1591356,29.1968946 11.2897839,29.3855453 11.4862475,29.456414 L14.4302554,30.5194455 C14.4833006,30.5384104 14.5383104,30.5483919 14.5943026,30.5483919 C14.6502947,30.5483919 14.7053045,30.5384104 14.7583497,30.5194455 L17.0530452,29.692976 L17.0530452,32.4388909 C17.0530452,32.6495009 17.1836935,32.8381516 17.3801572,32.9090203 L20.324165,33.9710536 C20.3772102,33.9900185 20.43222,34 20.4882122,34 C20.5442043,34 20.5992141,33.9900185 20.6522593,33.9710536 L23.6021611,32.9090203 C23.7976424,32.8381516 23.9292731,32.6495009 23.9292731,32.4388909 L23.9292731,29.692976 L26.2180747,30.5194455 C26.2711198,30.5384104 26.3261297,30.5483919 26.3821218,30.5483919 C26.4381139,30.5483919 26.4931238,30.5384104 26.546169,30.5194455 L29.4960707,29.456414 C29.6915521,29.3855453 29.8231827,29.1978928 29.8231827,28.9862847 L29.8231827,24.556488 C29.8222004,24.3418854 29.6886051,24.1512384 29.4882122,24.0833641 L29.4882122,24.0833641 Z M33,17.6063586 C33,20.6826617 26.302554,22.3425878 20,22.3425878 C13.697446,22.3425878 7,20.6826617 7,17.6063586 C7,16.1430684 8.60412574,14.8524584 11.5196464,13.9720887 L11.7996071,14.9283179 C9.44499018,15.64 7.98231827,16.6660998 7.98231827,17.6063586 C7.98231827,19.3750832 12.9174853,21.3444362 20,21.3444362 C27.0825147,21.3444362 32.0176817,19.3750832 32.0176817,17.6063586 C32.0176817,16.8836969 31.154224,16.0971534 29.6483301,15.4503512 L30.0324165,14.5310536 C32.4852652,15.5860998 33,16.785878 33,17.6063586 L33,17.6063586 Z M20.4911591,8.03009242 L25.9390963,10.0443623 L20.4911591,12.0825878 L15.043222,10.0443623 L20.4911591,8.03009242 Z M26.1090373,18.1693161 C25.1011788,18.6284658 23.4076621,19.1624769 20.9823183,19.229353 L20.9823183,12.9629575 L26.8762279,10.7570425 L26.8762279,16.9755268 C26.8762279,17.4875786 26.5746562,17.9567098 26.1090373,18.1693161 L26.1090373,18.1693161 Z M14.1060904,16.9755268 L14.1060904,10.7570425 L20,12.9629575 L20,19.229353 C17.5746562,19.1624769 15.8811395,18.6284658 14.8742633,18.1693161 C14.4076621,17.9567098 14.1060904,17.4875786 14.1060904,16.9755268 L14.1060904,16.9755268 Z M14.4724951,19.0796303 C15.6345776,19.6096488 17.6218075,20.2404806 20.4911591,20.2404806 C23.3605108,20.2404806 25.3477407,19.6096488 26.5108055,19.0796303 C27.3290766,18.7063216 27.8585462,17.8798521 27.8585462,16.9755268 L27.8585462,10.0413678 L27.8585462,10.0403697 C27.8585462,9.83075786 27.7288802,9.64410351 27.5353635,9.5722366 L20.6591356,7.02994455 C20.5510806,6.99001848 20.4302554,6.99001848 20.3231827,7.02994455 L13.4469548,9.5722366 C13.2534381,9.64410351 13.1237721,9.83075786 13.1237721,10.0403697 L13.1237721,10.0413678 L13.1237721,16.9755268 C13.1237721,17.8798521 13.6532417,18.7063216 14.4724951,19.0796303 L14.4724951,19.0796303 Z"
          id="AWS-Fargate_Icon_32_Squid"
          fill="#FFFFFF"
        />
      </g>
    </svg>
  );
};

const jupyterIcon = () => {
  return (
    <svg
      width={44}
      height={51}
      viewBox="0 0 44 51"
      xmlns="http://www.w3.org/2000/svg"
      xmlnsXlink="http://www.w3.org/1999/xlink"
    >
      <title>{'Group.svg'}</title>
      <g
        style={{
          mixBlendMode: 'normal'
        }}
      >
        <g
          style={{
            mixBlendMode: 'normal'
          }}
        >
          <use
            xlinkHref="#prefix__path0_fill"
            transform="translate(.54 21.36)"
            fill="#4E4E4E"
            style={{
              mixBlendMode: 'normal'
            }}
          />
          <use
            xlinkHref="#prefix__path1_fill"
            transform="translate(5.68 21.37)"
            fill="#4E4E4E"
            style={{
              mixBlendMode: 'normal'
            }}
          />
          <use
            xlinkHref="#prefix__path2_fill"
            transform="translate(13.39 21.26)"
            fill="#4E4E4E"
            style={{
              mixBlendMode: 'normal'
            }}
          />
          <use
            xlinkHref="#prefix__path3_fill"
            transform="translate(20.43 21.39)"
            fill="#4E4E4E"
            style={{
              mixBlendMode: 'normal'
            }}
          />
          <use
            xlinkHref="#prefix__path4_fill"
            transform="translate(27.55 19.54)"
            fill="#4E4E4E"
            style={{
              mixBlendMode: 'normal'
            }}
          />
          <use
            xlinkHref="#prefix__path5_fill"
            transform="translate(32.47 21.29)"
            fill="#4E4E4E"
            style={{
              mixBlendMode: 'normal'
            }}
          />
          <use
            xlinkHref="#prefix__path6_fill"
            transform="translate(39.98 21.24)"
            fill="#4E4E4E"
            style={{
              mixBlendMode: 'normal'
            }}
          />
        </g>
        <g
          style={{
            mixBlendMode: 'normal'
          }}
        >
          <use
            xlinkHref="#prefix__path7_fill"
            transform="translate(33.48 .69)"
            fill="#767677"
            style={{
              mixBlendMode: 'normal'
            }}
          />
          <use
            xlinkHref="#prefix__path8_fill"
            transform="translate(3.21 31.27)"
            fill="#F37726"
            style={{
              mixBlendMode: 'normal'
            }}
          />
          <use
            xlinkHref="#prefix__path9_fill"
            transform="translate(3.21 4.88)"
            fill="#F37726"
            style={{
              mixBlendMode: 'normal'
            }}
          />
          <use
            xlinkHref="#prefix__path10_fill"
            transform="translate(3.28 43.09)"
            fill="#9E9E9E"
            style={{
              mixBlendMode: 'normal'
            }}
          />
          <use
            xlinkHref="#prefix__path11_fill"
            transform="translate(1.87 5.43)"
            fill="#616262"
            style={{
              mixBlendMode: 'normal'
            }}
          />
        </g>
      </g>
      <defs>
        <path
          id="prefix__path0_fill"
          d="M1.745 5.475c0 1.558-.125 2.066-.445 2.44a1.94 1.94 0 01-1.3.498l.125.89a3.045 3.045 0 002.03-.738 3.561 3.561 0 00.783-2.671V0H1.745V5.475z"
        />
        <path
          id="prefix__path1_fill"
          d="M5.502 4.763c0 .668 0 1.264.053 1.78H4.496l-.071-1.059A2.466 2.466 0 012.26 6.695C1.23 6.695 0 6.135 0 3.846V.045h1.193v3.56c0 1.238.383 2.066 1.46 2.066A1.665 1.665 0 004.336 3.99V0h1.193v4.727l-.027.036z"
        />
        <path
          id="prefix__path2_fill"
          d="M.053 2.273c0-.828 0-1.505-.053-2.12h1.068l.054 1.114A2.582 2.582 0 013.454.002c1.585 0 2.778 1.327 2.778 3.303 0 2.333-1.433 3.49-2.982 3.49a2.306 2.306 0 01-2.021-1.023v3.56H.053V2.274zM1.23 4.009c.003.161.02.322.053.48a1.834 1.834 0 001.78 1.38c1.256 0 1.995-1.023 1.995-2.51 0-1.3-.695-2.413-1.95-2.413a2.048 2.048 0 00-1.878 1.95v1.113z"
        />
        <path
          id="prefix__path3_fill"
          d="M1.318.018L2.75 3.855c.151.427.312.944.418 1.327.125-.392.259-.89.419-1.354l1.3-3.81h1.255l-1.78 4.63c-.89 2.225-1.434 3.374-2.253 4.068a3.24 3.24 0 01-1.46.766l-.294-.997a3.16 3.16 0 001.042-.58 3.561 3.561 0 001.006-1.317.89.89 0 00.098-.285 1.024 1.024 0 00-.08-.311L0 0h1.3l.018.018z"
        />
        <path
          id="prefix__path4_fill"
          d="M2.19 0v1.87H3.9v.89H2.19v3.508c0 .801.232 1.264.89 1.264.234.004.468-.023.695-.08l.053.89c-.34.118-.7.172-1.06.16a1.656 1.656 0 01-1.29-.498 2.395 2.395 0 01-.463-1.692V2.751H0v-.89h1.033V.276L2.19 0z"
        />
        <path
          id="prefix__path5_fill"
          d="M1.177 3.579A2.092 2.092 0 003.43 5.831a4.345 4.345 0 001.78-.338l.205.89a5.342 5.342 0 01-2.181.401A3.027 3.027 0 01.01 3.508C.01 1.549 1.177 0 3.082 0 5.22 0 5.753 1.87 5.753 3.063c.012.183.012.368 0 .552H1.15l.027-.036zm3.49-.89A1.683 1.683 0 003.011.766a1.968 1.968 0 00-1.825 1.923h3.481z"
        />
        <path
          id="prefix__path6_fill"
          d="M.053 2.192c0-.765 0-1.424-.053-2.03h1.068v1.274h.054A1.968 1.968 0 012.902.01a1.3 1.3 0 01.339 0v1.113a1.78 1.78 0 00-.41 0 1.665 1.665 0 00-1.593 1.513 3.293 3.293 0 00-.054.552v3.464H.01V2.2l.044-.009z"
        />
        <path
          id="prefix__path7_fill"
          d="M6.03 2.836A3.018 3.018 0 112.889.005a2.982 2.982 0 013.143 2.83z"
        />
        <path
          id="prefix__path8_fill"
          d="M18.696 7.122C10.684 7.122 3.641 4.247 0 0a19.934 19.934 0 0037.392 0C33.76 4.247 26.744 7.122 18.696 7.122z"
        />
        <path
          id="prefix__path9_fill"
          d="M18.696 5.897c8.013 0 15.055 2.876 18.696 7.123A19.934 19.934 0 000 13.02c3.641-4.256 10.648-7.123 18.696-7.123z"
        />
        <path
          id="prefix__path10_fill"
          d="M7.596 3.567A3.802 3.802 0 113.634.005a3.766 3.766 0 013.962 3.562z"
        />
        <path
          id="prefix__path11_fill"
          d="M2.25 4.38A2.19 2.19 0 114.379 2.1a2.217 2.217 0 01-2.127 2.28z"
        />
      </defs>
    </svg>
  );
};

const sparkIcon = () => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      xmlnsXlink="http://www.w3.org/1999/xlink"
      width={44}
      height={51}
      viewBox="0 0 86 46"
      fill="#fff"
      fillRule="evenodd"
      stroke="#000"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <use xlinkHref="#prefix__a" x={0.5} y={0.5} />
      <symbol id="prefix__a" overflow="visible">
        <g stroke="none">
          <path
            d="M77.379 22.198l-.146-.31-3.186-6.04a.366.366 0 01.053-.494l5.04-5.922a.55.55 0 00.135-.266l-1.472.385-6.109 1.635c-.189.051-.276-.005-.37-.162L67.84 5.225a.79.79 0 00-.253-.282l-.289 1.544-.968 5.454-.1.59c-.016.188-.112.257-.282.311l-7.196 2.275a.882.882 0 00-.321.179l5.915 2.351-.173.137-3.679 2.381c-.146.096-.263.109-.427.035l-4.403-1.962c-.659-.294-1.25-.685-1.712-1.25-1.044-1.276-.837-2.728.553-3.614a6.56 6.56 0 011.486-.676l7.069-2.246a.4.4 0 00.327-.365l.968-5.453c.175-.962.269-1.968.741-2.859.192-.342.399-.677.658-.965.936-1.039 2.243-1.079 3.232-.09.334.334.621.728.87 1.133l3.232 5.36a.344.344 0 00.473.192l7.887-2.095c.543-.144 1.093-.196 1.65-.091 1.214.227 1.744 1.151 1.333 2.323-.187.534-.51.985-.871 1.411l-5.493 6.489c-.151.176-.154.304-.05.5l3.284 6.226c.262.497.462 1.013.467 1.583.013 1.298-.936 2.359-2.226 2.549-.721.096-1.395-.048-2.07-.257l-4.953-1.508a.28.28 0 01-.239-.271l-.598-3.486c-.006-.032.004-.067.01-.138l5.689 1.57"
            fill="#e25a1c"
          />
          <g fill="#3c3a3e">
            <path d="M74.164 39.139l-4.463-.004a.432.432 0 01-.417-.224l-5.513-8.349-1.125 8.554H58.75l.135-1.112 2.241-17.024a.355.355 0 01.135-.231l4.04-2.597c.019-.012.048-.014.115-.034L64.2 27.377l.048.033 6.375-7.067.627 3.62c.033.177-.014.288-.133.411l-4.084 4.292-.192.192.125.198 7.04 9.878c.042.06.104.096.157.16v.052m-46.167-8.558c-.06-.304-.102-.75-.237-1.166-.652-2.012-2.717-3.116-4.854-2.619-2.345.545-4.02 2.389-4.263 4.78-.18 1.77.773 3.475 2.546 4.115 1.427.516 2.802.3 4.078-.465 1.693-1.015 2.609-2.522 2.732-4.646zM17.7 38.058l-.334 2.499-.421 3.257c-.016.127-.055.192-.19.192l-3.21-.005c-.024 0-.048-.014-.096-.029l.195-1.539.712-5.401.842-6.171c.621-3.621 3.693-6.733 7.298-7.518 2.09-.452 4.09-.242 5.915.933 1.82 1.173 2.863 2.885 3.101 5.016.337 3.027-.777 5.54-2.928 7.618-1.411 1.366-3.101 2.231-5.05 2.525-2.007.303-3.895-.032-5.578-1.216-.062-.043-.129-.081-.236-.148M15.956 20.85l-3.518 2.619-.551-.864c-.504-.704-1.13-1.231-2.039-1.295a2.28 2.28 0 00-1.92.755 1.34 1.34 0 00-.09 1.773 25.32 25.32 0 001.524 1.784l2.67 2.826c.794.871 1.427 1.849 1.623 3.039.233 1.416-.05 2.764-.719 4.009-1.25 2.303-3.191 3.64-5.768 4.057-1.138.185-2.273.148-3.384-.179-1.474-.433-2.501-1.399-3.159-2.763-.233-.481-.412-.991-.623-1.508l3.816-2.042.115.277c.216.433.385.895.673 1.295.796 1.183 2.083 1.545 3.389.959.34-.154.654-.358.933-.606.841-.746.998-1.786.385-2.726-.358-.539-.805-1.023-1.25-1.507l-3.14-3.463c-.702-.811-1.177-1.757-1.327-2.843a4.88 4.88 0 01.69-3.304C5.82 18.661 8.051 17.37 11 17.477c1.681.061 3.02.846 4.059 2.154l.911 1.207m28.481 13.337l-.572 4.336c-.01.072-.067.169-.128.198-2.903 1.345-6.726 1.157-9.11-1.55-1.281-1.454-1.828-3.181-1.738-5.102.186-4.446 3.872-8.327 8.272-8.87 2.576-.317 4.834.379 6.579 2.38 1.189 1.363 1.738 2.982 1.657 4.787-.054 1.187-.24 2.368-.388 3.559l-.659 5.015c-.008.06-.019.118-.034.192h-3.463l.138-1.135.748-5.792c.137-1.204.051-2.4-.5-3.515-.577-1.186-1.568-1.813-2.86-1.95-2.674-.283-5.219 1.575-5.79 4.207-.377 1.737.217 3.403 1.6 4.323 1.348.897 2.793.9 4.263.317.745-.294 1.38-.762 1.984-1.392m14.625-10.657l-.474 3.601c-.734 0-1.454-.004-2.174.002a1.37 1.37 0 00-1.291.926c-.067.214-.094.442-.123.673l-1.091 8.296-.272 2.103h-3.62l.198-1.56.708-5.375.631-4.648c.325-2.071 2.385-3.909 4.474-4.001l3.028-.008" />
            <g fillRule="nonzero">
              <use xlinkHref="#prefix__C" />
              <path d="M27.171 16.613h-.531l-.179 1.005h.531c.32 0 .577-.212.577-.608a.36.36 0 00-.397-.397zm-1.286-.866h1.395c.731 0 1.25.435 1.25 1.183 0 .941-.666 1.575-1.613 1.575h-.601l-.282 1.594h-.908l.768-4.352" />
              <use xlinkHref="#prefix__C" x={10.811} />
              <path d="M38.54 19.935a2.384 2.384 0 01-.986.224c-1.151 0-1.876-.866-1.876-1.946 0-1.382 1.154-2.547 2.549-2.547a1.88 1.88 0 01.914.224l-.128 1.044c-.192-.212-.5-.359-.883-.359-.794 0-1.498.718-1.498 1.539 0 .635.396 1.125 1.024 1.125a1.62 1.62 0 001.004-.352l-.122 1.037m5.555-1.59H42.2l-.308 1.753h-.908l.767-4.352h.909l-.308 1.731h1.895l.308-1.731h.909l-.767 4.352h-.909l.308-1.753m3.332 1.754l.768-4.352H50.6l-.154.866H48.95l-.154.845h1.382l-.154.877h-1.392l-.154.877h1.504l-.154.877h-2.412" />
            </g>
          </g>
        </g>
      </symbol>
      <defs>
        <path
          id="prefix__C"
          d="M20.797 18.285h.896l-.212-1.347zm1.037.877h-1.491l-.474.928h-1.056l2.331-4.362h1.018l.794 4.352h-.979l-.14-.928"
        />
      </defs>
    </svg>
  );
};

export const Ec2Icon = (props: React.SVGProps<SVGSVGElement>): JSX.Element => {
  // NickC - adding eslint ignore on next line as Icon type doesn't match to JSX.Element
  // eslint-disable-next-line @typescript-eslint/ban-ts-ignore
  // @ts-ignore
  return <Icon component={ec2Svg} {...props} />;
};

export const FargateIcon = (
  props: React.SVGProps<SVGSVGElement>
): JSX.Element => {
  // NickC - adding eslint ignore on next line as Icon type doesn't match to JSX.Element
  // eslint-disable-next-line @typescript-eslint/ban-ts-ignore
  // @ts-ignore
  return <Icon component={fargateIcon} {...props} />;
};

export const JupyterIcon = (
  props: React.SVGProps<SVGSVGElement>
): JSX.Element => {
  // stthoom - adding eslint ignore on next line as Icon type doesn't match to JSX.Element
  // eslint-disable-next-line @typescript-eslint/ban-ts-ignore
  // @ts-ignore
  return <Icon component={jupyterIcon} {...props} />;
};

export const SparkIcon = (
  props: React.SVGProps<SVGSVGElement>
): JSX.Element => {
  // stthoom - adding eslint ignore on next line as Icon type doesn't match to JSX.Element
  // eslint-disable-next-line @typescript-eslint/ban-ts-ignore
  // @ts-ignore
  return <Icon component={sparkIcon} {...props} />;
};
