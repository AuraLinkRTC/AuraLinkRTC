"""
Resilience patterns for AuraLink services
Includes circuit breaker and retry/backoff utilities
"""

import asyncio
import time
import random
from enum import Enum
from typing import Callable, Optional, Any, TypeVar, List
from dataclasses import dataclass
from datetime import datetime, timedelta

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""
    pass


class MaxRetriesExceededError(Exception):
    """Raised when max retries are exceeded"""
    pass


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    name: str
    max_failures: int = 5
    timeout_seconds: float = 60.0
    max_requests: int = 1
    interval_seconds: float = 60.0


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics"""
    name: str
    state: CircuitState
    failures: int
    successes: int
    requests: int
    last_failure_time: Optional[datetime]
    last_state_change: datetime


class CircuitBreaker:
    """Circuit breaker implementation for Python services"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.name = config.name
        self.max_failures = config.max_failures
        self.timeout = timedelta(seconds=config.timeout_seconds)
        self.max_requests = config.max_requests
        self.interval = timedelta(seconds=config.interval_seconds)
        
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.successes = 0
        self.requests = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_state_change = datetime.now()
        
        self._lock = asyncio.Lock()
    
    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute a function with circuit breaker protection"""
        await self._before_request()
        
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise e
    
    async def _before_request(self):
        """Check if request can proceed"""
        async with self._lock:
            now = datetime.now()
            
            if self.state == CircuitState.OPEN:
                # Check if timeout has passed
                if now - self.last_state_change > self.timeout:
                    self._set_state(CircuitState.HALF_OPEN, now)
                    self.requests = 0
                    self.successes = 0
                    self.failures = 0
                else:
                    raise CircuitBreakerError(f"Circuit breaker '{self.name}' is open")
            
            elif self.state == CircuitState.HALF_OPEN:
                if self.requests >= self.max_requests:
                    raise CircuitBreakerError(f"Too many requests in half-open state")
                self.requests += 1
            
            elif self.state == CircuitState.CLOSED:
                # Reset failures if interval has passed
                if now - self.last_state_change > self.interval:
                    self.failures = 0
                    self.last_state_change = now
    
    async def _on_success(self):
        """Handle successful request"""
        async with self._lock:
            now = datetime.now()
            
            if self.state == CircuitState.HALF_OPEN:
                self.successes += 1
                if self.successes >= self.max_requests:
                    self._set_state(CircuitState.CLOSED, now)
                    self.failures = 0
                    self.successes = 0
                    self.requests = 0
    
    async def _on_failure(self):
        """Handle failed request"""
        async with self._lock:
            now = datetime.now()
            self.failures += 1
            self.last_failure_time = now
            
            if self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open reopens the circuit
                self._set_state(CircuitState.OPEN, now)
                self.requests = 0
                self.successes = 0
            
            elif self.state == CircuitState.CLOSED:
                if self.failures >= self.max_failures:
                    self._set_state(CircuitState.OPEN, now)
    
    def _set_state(self, state: CircuitState, now: datetime):
        """Change circuit breaker state"""
        self.state = state
        self.last_state_change = now
    
    def get_state(self) -> CircuitState:
        """Get current state"""
        return self.state
    
    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics"""
        return CircuitBreakerStats(
            name=self.name,
            state=self.state,
            failures=self.failures,
            successes=self.successes,
            requests=self.requests,
            last_failure_time=self.last_failure_time,
            last_state_change=self.last_state_change
        )


@dataclass
class RetryConfig:
    """Retry configuration"""
    max_attempts: int = 3
    initial_delay_seconds: float = 0.1
    max_delay_seconds: float = 10.0
    multiplier: float = 2.0
    randomization_factor: float = 0.1
    retryable_exceptions: Optional[List[type]] = None


async def retry_async(
    func: Callable[..., T],
    config: Optional[RetryConfig] = None,
    *args,
    **kwargs
) -> T:
    """
    Retry an async function with exponential backoff
    
    Args:
        func: Async function to retry
        config: Retry configuration
        *args: Function arguments
        **kwargs: Function keyword arguments
    
    Returns:
        Function result
    
    Raises:
        MaxRetriesExceededError: When max retries exceeded
    """
    if config is None:
        config = RetryConfig()
    
    last_exception = None
    delay = config.initial_delay_seconds
    
    for attempt in range(1, config.max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            # Check if error is retryable
            if config.retryable_exceptions:
                if not any(isinstance(e, exc_type) for exc_type in config.retryable_exceptions):
                    raise e
            
            # Last attempt, don't wait
            if attempt == config.max_attempts:
                break
            
            # Calculate backoff with jitter
            backoff_delay = _calculate_backoff(
                delay,
                config.max_delay_seconds,
                config.multiplier,
                config.randomization_factor
            )
            
            await asyncio.sleep(backoff_delay)
            delay = backoff_delay
    
    raise MaxRetriesExceededError(
        f"Max retries ({config.max_attempts}) exceeded. Last error: {last_exception}"
    )


def retry_sync(
    func: Callable[..., T],
    config: Optional[RetryConfig] = None,
    *args,
    **kwargs
) -> T:
    """
    Retry a sync function with exponential backoff
    
    Args:
        func: Function to retry
        config: Retry configuration
        *args: Function arguments
        **kwargs: Function keyword arguments
    
    Returns:
        Function result
    
    Raises:
        MaxRetriesExceededError: When max retries exceeded
    """
    if config is None:
        config = RetryConfig()
    
    last_exception = None
    delay = config.initial_delay_seconds
    
    for attempt in range(1, config.max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            # Check if error is retryable
            if config.retryable_exceptions:
                if not any(isinstance(e, exc_type) for exc_type in config.retryable_exceptions):
                    raise e
            
            # Last attempt, don't wait
            if attempt == config.max_attempts:
                break
            
            # Calculate backoff with jitter
            backoff_delay = _calculate_backoff(
                delay,
                config.max_delay_seconds,
                config.multiplier,
                config.randomization_factor
            )
            
            time.sleep(backoff_delay)
            delay = backoff_delay
    
    raise MaxRetriesExceededError(
        f"Max retries ({config.max_attempts}) exceeded. Last error: {last_exception}"
    )


def _calculate_backoff(
    current_delay: float,
    max_delay: float,
    multiplier: float,
    randomization_factor: float
) -> float:
    """Calculate next backoff delay with jitter"""
    # Apply multiplier
    next_delay = current_delay * multiplier
    
    # Cap at max
    if next_delay > max_delay:
        next_delay = max_delay
    
    # Apply jitter
    if randomization_factor > 0:
        delta = randomization_factor * next_delay
        min_delay = next_delay - delta
        max_jitter = next_delay + delta
        next_delay = min_delay + random.random() * (max_jitter - min_delay)
    
    return next_delay


class ExponentialBackoff:
    """Exponential backoff strategy"""
    
    def __init__(
        self,
        initial_interval: float = 0.5,
        max_interval: float = 60.0,
        multiplier: float = 1.5,
        randomization_factor: float = 0.5
    ):
        self.initial_interval = initial_interval
        self.max_interval = max_interval
        self.multiplier = multiplier
        self.randomization_factor = randomization_factor
        self.current_interval = initial_interval
    
    def next_backoff(self) -> float:
        """Get next backoff duration"""
        # Calculate next interval
        next_interval = self.current_interval * self.multiplier
        
        # Cap at max
        if next_interval > self.max_interval:
            next_interval = self.max_interval
        
        # Apply randomization
        delta = self.randomization_factor * next_interval
        min_interval = next_interval - delta
        max_interval = next_interval + delta
        
        random_interval = min_interval + random.random() * (max_interval - min_interval)
        
        self.current_interval = next_interval
        return random_interval
    
    def reset(self):
        """Reset to initial interval"""
        self.current_interval = self.initial_interval


class ConstantBackoff:
    """Constant backoff strategy"""
    
    def __init__(self, interval: float = 1.0):
        self.interval = interval
    
    def next_backoff(self) -> float:
        """Get next backoff duration"""
        return self.interval
    
    def reset(self):
        """No-op for constant backoff"""
        pass


class LinearBackoff:
    """Linear backoff strategy"""
    
    def __init__(
        self,
        initial_interval: float = 0.5,
        max_interval: float = 30.0,
        increment: float = 0.5
    ):
        self.initial_interval = initial_interval
        self.max_interval = max_interval
        self.increment = increment
        self.current_interval = initial_interval
    
    def next_backoff(self) -> float:
        """Get next backoff duration"""
        current = self.current_interval
        
        # Increment for next time
        next_val = self.current_interval + self.increment
        if next_val > self.max_interval:
            next_val = self.max_interval
        
        self.current_interval = next_val
        return current
    
    def reset(self):
        """Reset to initial interval"""
        self.current_interval = self.initial_interval
