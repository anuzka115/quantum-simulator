import React from 'react';
import styled from 'styled-components';

const LoadAnimation = () => {
  return (
    <StyledWrapper>
      <div className="loader">
        <div className="loader-inner"> 
          <div className="loader-block" />
          <div className="loader-block" />
          <div className="loader-block" />
          <div className="loader-block" />
          <div className="loader-block" />
          <div className="loader-block" />
          <div className="loader-block" />
          <div className="loader-block" />
          <div className="loader-block" />
          <div className="loader-block" />
         
    
        </div>
      </div>
    </StyledWrapper>
  );
}

const StyledWrapper = styled.div`
  .loader {
    display: flex;
    justify-content: center;
    align-items: center;
    width: 80px;
    height: 80px;
    position: relative;
  }

  .loader:before {
    content: "";
    position: absolute;
    top: -10px;
    left: -10px;
    right: -10px;
    bottom: -10px;
    border-radius: 50%;
  }

  .loader-inner {
    display: flex;
    justify-content: center;
    align-items: center;
    position: relative;
  }

  .loader-block {
    display: inline-block;
    width: 8px;
    height: 10px;
    margin: 2px;
    background-color: rgb(53, 143, 246);
    box-shadow: 0 0 30px rgb(53, 143, 246);
    animation: loader 5s infinite;
  }

  .loader-block:nth-child(1) {
    animation-delay: 0.2s;
  }

  .loader-block:nth-child(2) {
    animation-delay: 0.4s;
  }

  .loader-block:nth-child(3) {
    animation-delay: 0.6s;
  }

  .loader-block:nth-child(4) {
    animation-delay: 0.8s;
  }

  .loader-block:nth-child(5) {
    animation-delay: 1s;
  }

  .loader-block:nth-child(6) {
    animation-delay: 1.2s;
  }

  .loader-block:nth-child(7) {
    animation-delay: 1.4s;
  }

  .loader-block:nth-child(8) {
    animation-delay: 1.6s;
  }

  .loader-block:nth-child(9) {
    animation-delay: 1.8s;
  }

  .loader-block:nth-child(10) {
    animation-delay: 2s;
  }

  .loader-block:nth-child(11) {
    animation-delay: 2.2s;
  }

  .loader-block:nth-child(12) {
    animation-delay: 2.4s;
  }

  .loader-block:nth-child(13) {
    animation-delay: 2.6s;
  }

  .loader-block:nth-child(14) {
    animation-delay: 2.8s;
  }

  .loader-block:nth-child(15) {
    animation-delay: 3s;
  }

  .loader-block:nth-child(16) {
    animation-delay: 3.2s;
  }

  .loader-block:nth-child(17) {
    animation-delay: 3.4s;
  }

  .loader-block:nth-child(18) {
    animation-delay: 3.6s;
  }

  .loader-block:nth-child(19) {
    animation-delay: 3.8s;
  }

  .loader-block:nth-child(20) {
    animation-delay: 4s;
  }

  .loader-block:nth-child(21) {
    animation-delay: 4.2s;
  }

  .loader-block:nth-child(22) {
    animation-delay: 4.4s;
  }

  .loader-block:nth-child(23) {
    animation-delay: 4.6s;
  }

  .loader-block:nth-child(24) {
    animation-delay: 4.8s;
  }

  @keyframes loader {
    0% {
      transform: scale(1);
      box-shadow: 0 0 40px rgb(53, 143, 246);
    }

    13% {
      transform: scale(1, 4);
      box-shadow: 0 0 60px rgb(53, 143, 246);
    }

    26% {
      transform: scale(1);
      box-shadow: 0 0 40px rgb(53, 143, 246);
    }
  }`;

export default LoadAnimation;
